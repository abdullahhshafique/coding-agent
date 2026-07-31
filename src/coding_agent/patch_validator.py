# coding_agent/patch_validator.py
"""Validate generated patches syntactically.

This validator is deliberately *lenient* about unified-diff format details
that LLM-generated diffs frequently get wrong (approximate hunk-header line
counts, missing trailing newlines, stray code fences), while remaining strict
about the two things that actually matter for safety:

1. The patch only touches files the agent actually read this run.
2. The patched result parses as valid Python.

LLMs rarely emit hunk headers with exact ``@@ -a,b +c,d @@`` counts, so a
strict parser (``unidiff``) or ``git apply --check`` rejects most real model
output. Rejecting those as "invalid" would force pointless regeneration
retries. Instead we parse hunk bodies ourselves, ignoring the header counts,
and apply hunks by matching context/removal lines against the original file.
A patch is rejected only if it is structurally unrecognizable as a diff,
references an unseen file, fails to apply cleanly, or produces invalid Python.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
_FENCE_RE = re.compile(r"```[a-zA-Z]*\n?(.*?)\n?```", re.DOTALL)


def _strip_prefix(path: str) -> str:
    """Strip a leading ``a/`` or ``b/`` git prefix from a diff path."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _hunk_old_start(header: str) -> int:
    """Extract the old-file start line from an ``@@`` header."""
    match = re.search(r"-(\d+)", header)
    return int(match.group(1)) if match else 1


@dataclass
class _HunkLine:
    """A single line inside a hunk body."""

    tag: str  # "context" | "remove" | "add"
    text: str


@dataclass
class _Hunk:
    """One ``@@`` block: a source start line plus its body lines."""

    old_start: int
    lines: list[_HunkLine] = field(default_factory=list)


@dataclass
class _FilePatch:
    """All hunks for one target file path."""

    path: str
    hunks: list[_Hunk] = field(default_factory=list)


@dataclass
class _ParseState:
    """Incremental state for the lenient line-by-line diff parser."""

    files: list[_FilePatch] = field(default_factory=list)
    current: _FilePatch | None = None
    current_hunk: _Hunk | None = None
    pending_old: str | None = None  # path seen on a "---" line

    def reset_file(self) -> None:
        """Reset per-file tracking at a ``diff --git`` boundary."""
        self.current = None
        self.current_hunk = None
        self.pending_old = None

    def start_file(self, path: str) -> None:
        """Begin a new file patch for ``path``."""
        self.current = _FilePatch(path=path)
        self.files.append(self.current)
        self.current_hunk = None
        self.pending_old = None

    def start_hunk(self, old_start: int) -> None:
        """Begin a new hunk under the current file.

        If no ``+++`` header set the current file but a ``---`` line supplied
        an old path, fall back to it; a hunk with no file context at all is
        ignored (not a usable diff).
        """
        if self.current is None and self.pending_old:
            self.start_file(_strip_prefix(self.pending_old))
        if self.current is None:
            return
        self.current_hunk = _Hunk(old_start=old_start)
        self.current.hunks.append(self.current_hunk)

    def add_body_line(self, line: str) -> None:
        """Add a line to the active hunk body, if any."""
        hunk = self.current_hunk
        if hunk is None:
            return
        if line.startswith("+"):
            hunk.lines.append(_HunkLine("add", line[1:]))
        elif line.startswith("-"):
            hunk.lines.append(_HunkLine("remove", line[1:]))
        elif line.startswith(" "):
            hunk.lines.append(_HunkLine("context", line[1:]))
        elif line == "":
            # A bare empty line is a context line with empty text.
            hunk.lines.append(_HunkLine("context", ""))
        elif line.startswith("\\"):
            pass  # "\ No newline at end of file" — ignore.
        # Any other line ends the hunk body (ignored leniently).


class PatchValidator:
    """Checks that a generated diff is syntactically valid and safely scoped."""

    def validate(
        self,
        diff_text: str,
        original_files: dict[str, str],
    ) -> tuple[bool, str | None]:
        """Validate a unified diff against the files it claims to touch.

        Args:
            diff_text: The raw unified diff emitted by the LLM.
            original_files: Map of repo-relative path -> original file content
                for every file the agent fetched this run.

        Returns:
            Tuple of (is_valid, error_message). error_message is None on success.
        """
        cleaned = self._clean_diff(diff_text)
        if not cleaned:
            return False, "Empty diff"

        file_patches = self._parse(cleaned)
        if not file_patches:
            return False, "Failed to parse diff: no file hunks found"

        for fp in file_patches:
            if fp.path not in original_files:
                return False, f"Patch references unseen file: {fp.path}"

            original = original_files[fp.path]
            try:
                patched = self._apply(fp, original)
            except ValueError as exc:
                return False, f"Failed to apply patch to {fp.path}: {exc}"

            if fp.path.endswith(".py"):
                try:
                    ast.parse(patched)
                except SyntaxError as exc:
                    return False, f"Syntax error in patched {fp.path}: {exc}"

        return True, None

    # -- Cleaning -----------------------------------------------------------

    def _clean_diff(self, diff_text: str) -> str:
        """Strip code fences, a trailing RATIONALE block, and stray backticks."""
        text = diff_text.strip()
        if not text:
            return ""

        # If fenced blocks are present, prefer their contents (models often
        # wrap only the diff even when told not to).
        matches = _FENCE_RE.findall(text)
        if matches:
            fenced = "\n".join(m.strip() for m in matches if m.strip())
            if fenced:
                text = fenced

        # Drop anything from a RATIONALE: marker onward.
        if "RATIONALE:" in text:
            text = text.split("RATIONALE:", 1)[0]

        return text.strip("`").strip()

    # -- Parsing ------------------------------------------------------------

    def _parse(self, text: str) -> list[_FilePatch]:
        """Parse cleaned diff text into per-file hunk lists.

        Lenient about hunk header counts; only structural markers (diff/---/+++
        headers and @@ hunks) matter. Returns an empty list if nothing that
        looks like a file patch is present.
        """
        state = _ParseState()
        for line in text.splitlines():
            self._parse_line(line, state)

        # Keep only files that actually have hunks with content.
        return [f for f in state.files if any(h.lines for h in f.hunks)]

    def _parse_line(self, line: str, state: _ParseState) -> None:
        """Feed one diff line into the incremental parse state."""
        if line.startswith("diff --git"):
            state.reset_file()
        elif line.startswith(("--- ", "---\t")):
            state.pending_old = line[4:].strip()
        elif line.startswith(("+++ ", "+++\t")):
            state.start_file(_strip_prefix(line[4:].strip()))
        elif _HUNK_HEADER_RE.match(line):
            state.start_hunk(_hunk_old_start(line))
        else:
            state.add_body_line(line)

    # -- Applying -----------------------------------------------------------

    def _apply(self, fp: _FilePatch, original: str) -> str:
        """Apply one file's hunks to its original content.

        Hunks are applied sequentially against a mutable line list. Each hunk
        tries its declared start line first, then searches for its leading
        context/removal sequence. Raises ValueError on failure.
        """
        lines = original.splitlines()
        offset = 0

        for hunk in fp.hunks:
            anchor_pos = self._locate(hunk, lines, hunk.old_start - 1 + offset)
            if anchor_pos is None:
                raise ValueError(f"hunk starting at line {hunk.old_start} not found")

            pos = anchor_pos
            delta = 0  # net line-count change introduced by this hunk
            for hl in hunk.lines:
                if hl.tag == "add":
                    # Insertion: emit before the next existing matched line.
                    lines.insert(pos, hl.text)
                    pos += 1
                    delta += 1
                    continue
                # context / remove must match the CURRENT line exactly. This
                # is deliberately strict: silently skipping past non-matching
                # lines here would let a fuzzy diff delete or leapfrog code it
                # never mentions, which a human reviewer would not expect.
                # Lenient *location* (above) handles fuzzy header offsets;
                # strict *application* keeps the edit auditable.
                if pos >= len(lines) or lines[pos] != hl.text:
                    raise ValueError(
                        f"{hl.tag} mismatch at line {pos + 1}: "
                        f"expected {hl.text!r}"
                    )
                if hl.tag == "context":
                    pos += 1
                else:  # remove
                    lines.pop(pos)
                    delta -= 1
            offset += delta

        return "\n".join(lines) + ("\n" if original.endswith("\n") else "")

    @staticmethod
    def _hunks_match(lines: list[str], start: int, key: list[str]) -> bool:
        """Return True if ``key`` lines appear in ``lines`` from ``start``.

        ``key`` (context + removal lines) is matched as an order-preserving
        subsequence: each line must appear at or after the previous match.
        This tolerates the extra/missing lines a wrong hunk header implies.
        """
        pos = start
        for want in key:
            found = False
            while pos < len(lines):
                if lines[pos] == want:
                    found = True
                    pos += 1
                    break
                pos += 1
            if not found:
                return False
        return True

    @staticmethod
    def _locate(hunk: _Hunk, lines: list[str], guess: int) -> int | None:
        """Find where a hunk applies, preferring the declared line, then near it.

        The anchor is the hunk's *first* non-added (context/removal) line,
        which must already exist in the original. Search radiates outward from
        the declared position so a wrong or fuzzy header offset still applies;
        ties prefer the nearer candidate, then the earlier one.
        """
        key = [hl.text for hl in hunk.lines if hl.tag != "add"]
        if not key:
            # Pure-insertion hunk: apply at the declared position (clamped).
            return max(0, min(guess, len(lines)))

        anchor = key[0]
        n = len(lines)
        best: int | None = None
        best_dist: int | None = None
        for cand in range(n):
            if lines[cand] != anchor:
                continue
            if not PatchValidator._hunks_match(lines, cand, key):
                continue
            dist = abs(cand - guess)
            if best_dist is None or dist < best_dist:
                best, best_dist = cand, dist
        return best
