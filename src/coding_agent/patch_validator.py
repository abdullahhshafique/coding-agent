"""Validate generated patches syntactically."""

from __future__ import annotations

import ast
from typing import Any

from unidiff import PatchSet


class PatchValidator:
    """Checks that a generated diff is syntactically valid."""

    def validate(
        self,
        diff_text: str,
        original_files: dict[str, str],
    ) -> tuple[bool, str | None]:
        """Validate a unified diff."""
        if not diff_text.strip():
            return False, "Empty diff"

        try:
            patch = PatchSet(diff_text)
        except Exception as exc:
            return False, f"Failed to parse diff: {exc}"

        for patched_file in patch:
            path = patched_file.path
            if path not in original_files:
                return False, f"Patch references unseen file: {path}"

            original = original_files[path]
            patched = self._apply_patch_to_file(patched_file, original)

            try:
                ast.parse(patched)
            except SyntaxError as exc:
                return False, f"Syntax error in patched {path}: {exc}"

        return True, None

    def _apply_patch_to_file(self, patched_file: Any, original: str) -> str:
        """Apply a single patched file to original content."""
        lines = original.splitlines(keepends=True)
        result_lines = list(lines)
        offset = 0

        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    insert_idx = line.target_line_no - 1 + offset
                    if insert_idx < 0:
                        insert_idx = 0
                    result_lines.insert(insert_idx, line.value)
                    offset += 1
                elif line.is_removed:
                    remove_idx = line.source_line_no - 1 + offset
                    if 0 <= remove_idx < len(result_lines):
                        result_lines.pop(remove_idx)
                        offset -= 1

        return "".join(result_lines)
