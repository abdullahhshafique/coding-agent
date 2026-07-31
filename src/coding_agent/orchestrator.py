"""Agent orchestrator driving the search to read to generate loop."""

from __future__ import annotations

import re
import uuid
from typing import Any

from coding_agent.ast_tool import ASTTool
from coding_agent.exceptions import (
    BudgetExhaustedError,
    CodingAgentError,
    GitHubNotFoundError,
)
from coding_agent.github_tool import GitHubTool
from coding_agent.llm_tool import LLMTool
from coding_agent.models import FileStructure, RunRequest, RunResult, RunState
from coding_agent.output_writer import OutputWriter
from coding_agent.patch_validator import PatchValidator
from coding_agent.trace_logger import TraceLogger


class AgentOrchestrator:
    """Drives the core agent loop: search to read to parse to generate to validate."""  # noqa: E501

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self.run_id = str(uuid.uuid4())
        self.trace_logger = TraceLogger(run_id=self.run_id)
        self.github = GitHubTool(self.trace_logger)
        self.ast = ASTTool(self.trace_logger)
        self._llm: LLMTool | None = None
        self.validator = PatchValidator()
        self.output_writer = OutputWriter()

    @property
    def llm(self) -> LLMTool:
        """Lazy-initialize LLM tool to avoid key check in tests."""
        if self._llm is None:
            self._llm = LLMTool(self.trace_logger)
        return self._llm

    def run(self, request: RunRequest) -> RunResult:
        """Execute a full agent run.

        Args:
            request: The run request with repo, issue text, and budget.

        Returns:
            RunResult with patch, rationale, and trace paths.
        """
        state = RunState(request=request, remaining_budget=request.tool_call_budget)

        try:
            return self._execute_run(state)
        except BudgetExhaustedError:
            return self._insufficient_context(state, "Tool-call budget exhausted")
        except GitHubNotFoundError:
            return self._insufficient_context(
                state, f"Repository {request.repo} not found"
            )
        except CodingAgentError as exc:
            # Every typed error in this project's own hierarchy (Rules.md
            # §5) represents a case where the agent correctly determined
            # it cannot proceed confidently -- a designed stopping
            # condition, not a system failure. Route all of them to the
            # insufficient-context path.
            return self._insufficient_context(state, str(exc))
        except Exception as exc:
            # Anything that reaches here is, by construction, NOT one of
            # this project's typed errors -- Rules.md §5 requires every
            # tool to raise a typed CodingAgentError subclass, so an
            # untyped exception surfacing here means something broke that
            # the typed-error contract didn't anticipate (a bug, an
            # unhandled library exception, etc.), not a graceful stop.
            # This is status="error", distinct from "insufficient_context",
            # so Evaluator's failed_patches count (PRD §4) actually means
            # something.
            return self._system_failure(state, f"Unexpected error: {exc}")

    def _execute_run(self, state: RunState) -> RunResult:
        """Core loop execution after initialization.

        Args:
            state: Current run state.

        Returns:
            RunResult with patch or failure reason.
        """
        owner, repo = self._parse_repo(state.request.repo)
        self._check_budget(state)
        self.github.validate_repo(owner, repo)

        issue_text = self._resolve_issue_text(state.request, owner, repo)
        if not issue_text or not issue_text.strip():
            return self._insufficient_context(
                state, "Empty or missing issue description"
            )

        self._check_budget(state)
        candidates = self._search_phase(state, owner, repo, issue_text)
        if not candidates:
            return self._insufficient_context(
                state, "No relevant files found via search"
            )

        self._check_budget(state)
        file_structures = self._read_and_parse_phase(state, owner, repo, candidates)
        if not file_structures:
            return self._insufficient_context(
                state, "Could not read/parse any candidate files"
            )

        self._check_budget(state)
        diff_text, rationale = self._generate_phase(state, issue_text, file_structures)

        original_files: dict[str, str] = {}
        for fs in file_structures:
            original_files[fs.path] = fs.raw_content

        is_valid, validation_error = self.validator.validate(diff_text, original_files)

        if not is_valid:
            self._check_budget(state)
            diff_text, rationale = self._generate_phase(
                state,
                issue_text,
                file_structures,
                retry_context=f"Previous patch invalid: {validation_error}",
            )
            is_valid, validation_error = self.validator.validate(
                diff_text, original_files
            )
            if not is_valid:
                return self._insufficient_context(
                    state,
                    f"Patch validation failed after retry: " f"{validation_error}",
                )

        return self.output_writer.write(
            repo=state.request.repo,
            diff_text=diff_text,
            rationale=rationale,
            trace_logger=self.trace_logger,
        )

    def _parse_repo(self, repo_str: str) -> tuple[str, str]:
        """Parse owner/repo from string or URL.

        Args:
            repo_str: Repository identifier or GitHub URL.

        Returns:
            Tuple of (owner, repo).
        """
        url_match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_str)
        if url_match:
            return url_match.group(1), url_match.group(2).rstrip(".git")

        if "/" in repo_str:
            parts = repo_str.split("/")
            return parts[0], parts[1]

        raise ValueError(f"Invalid repo format: {repo_str}")

    def _resolve_issue_text(self, request: RunRequest, owner: str, repo: str) -> str:
        """Resolve issue text from URL or raw text.

        Per PRD §6.1: if both an issue URL and raw text are given, the URL
        text takes precedence and the raw text is kept as supplementary
        context appended after it -- not discarded.

        Args:
            request: The run request.
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Resolved issue text.
        """
        if request.issue_url:
            match = re.search(r"/issues/(\d+)", request.issue_url)
            if match:
                number = int(match.group(1))
                url_text = self.github.get_issue(owner, repo, number)
                if request.issue_text and request.issue_text.strip():
                    return (
                        url_text
                        + "\n\n"
                        + "Additional context supplied by user:"
                        + "\n"
                        + request.issue_text
                    )
                return url_text
        return request.issue_text or ""

    def _search_phase(
        self, state: RunState, owner: str, repo: str, issue_text: str
    ) -> list[dict[str, Any]]:
        """Search for candidate files.

        Args:
            state: Current run state.
            owner: Repository owner.
            repo: Repository name.
            issue_text: Bug description.

        Returns:
            List of search result items.
        """
        ident_terms = self._extract_identifiers(issue_text)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Strategy 1 (primary): one query per extracted code identifier.
        # Code search ANDs multiple terms, so a single honest identifier per
        # query is what reliably lexically matches source. Merge + dedupe.
        for term in ident_terms:
            for item in self._search_github(state, f"repo:{owner}/{repo} {term}"):
                path = item.get("path", "")
                if path not in seen:
                    seen.add(path)
                    results.append(item)
            if len(results) >= 3:
                break  # enough candidates; save remaining budget for reads

        # Strategy 2 (fallback): the raw keyword query, only if identifiers
        # surfaced nothing usable (e.g. a genuinely vague report with no named
        # symbol). Preserved from the original loop for the hard-case path.
        if len(results) < 1:
            keywords = self._extract_keywords(issue_text)
            for item in self._search_github(state, f"repo:{owner}/{repo} {keywords}"):
                path = item.get("path", "")
                if path not in seen:
                    seen.add(path)
                    results.append(item)

        return self._rank_candidates(results)

    # File names / dirs that are documentation or metadata, not patchable
    # code. Keyword search frequently surfaces these and, if ranked first,
    # they crowd out the actual source file (PRD §6.2 edge case: too many /
    # noisy results must be filtered, not all read).
    _NOISE_FILENAMES = (
        "changes", "changelog", "history", "news", "authors",
        "contributors", "license", "readme", "contributing", "codeofconduct",
    )
    _NOISE_DIRS = ("docs/", "doc/", ".github/", "examples/", "example/")

    def _rank_candidates(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Drop doc/metadata matches and rank source files above the rest.

        Returns the filtered list with patchable source files first, then any
        other (non-noise) files as secondary context.
        """
        source: list[dict[str, Any]] = []
        other: list[dict[str, Any]] = []
        for item in results:
            path = item.get("path", "")
            lower = path.lower()
            base = lower.rsplit("/", 1)[-1]
            stem = base.split(".")[0]
            if stem in self._NOISE_FILENAMES or lower.endswith(
                (".md", ".rst", ".txt")
            ) or any(lower.startswith(d) for d in self._NOISE_DIRS):
                continue  # documentation/metadata — not a patch target
            # Tests are reference material, not patch targets; reading them
            # burns the LLM's token budget without producing an applyable
            # diff. Drop them from candidates.
            if (
                base.startswith("test_")
                or base.endswith("_test.py")
                or "/tests/" in lower
                or lower.startswith(("tests/", "test/"))
            ):
                continue
            if lower.endswith(".py"):
                source.append(item)
            else:
                other.append(item)
        return source + other

    def _extract_keywords(self, issue_text: str) -> str:
        """Extract search keywords from issue text.

        Args:
            issue_text: Raw issue description.

        Returns:
            Space-separated keywords.
        """
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "ought",
            "used",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "and",
            "but",
            "or",
            "yet",
            "so",
            "if",
            "because",
            "although",
            "though",
            "while",
            "where",
            "when",
            "that",
            "which",
            "who",
            "whom",
            "whose",
            "what",
            "this",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "its",
            "our",
            "their",
        }
        punctuation = ".,;:!?()[]{}\\\"'"
        words = issue_text.lower().split()
        keywords = [
            w.strip(punctuation)
            for w in words
            if w.strip(punctuation) not in stop_words
        ]
        return " ".join(keywords[:10])

    # A code identifier must contain at least one underscore or uppercase
    # letter — plain lowercase words are prose, not symbol names, and the
    # code search lexer AND-combines them so adding prose kills precision.
    _IDENT_RE = re.compile(r"\b(?=[\w()]*[_A-Z])([\w.]+\(\)|[\w.]+)\b")

    def _extract_identifiers(self, issue_text: str, limit: int = 3) -> list[str]:
        """Extract search terms that name actual code symbols.

        GitHub code search is a lexical matcher: it finds a term only if that
        exact (sub-)string appears in a file. Bug prose ("the usage line is not
        printed") almost never lexically matches code, so raw keyword queries
        return noise (CHANGES.md) or nothing. Code identifiers from the report
        — backticked names, ``snake_case`` / ``CamelCase`` symbols, dotted
        paths — are the terms that actually lexically match. Extracted in
        order of decreasing signal: longer and more structured names first.

        Args:
            issue_text: The raw issue/bug description.
            limit: Maximum number of identifiers to return.

        Returns:
            Up to ``limit`` identifier strings, deduplicated, best first.
        """
        candidates: list[str] = []
        # 1) backticked spans are the highest-signal source of exact symbols
        for span in re.findall(r"`([^`]+)`", issue_text):
            candidates.extend(re.split(r"[^\w.()]+", span))
        # 2) snake_case, CamelCase, and dotted identifiers in prose
        candidates.extend(self._IDENT_RE.findall(issue_text))

        seen: set[str] = set()
        idents: list[str] = []
        for raw in candidates:
            term = raw.strip("()")
            # keep only tokens that carry code structure; skip short/common
            if len(term) < 4 or not re.search(r"[_./A-Z]", term):
                continue
            term = term.split(".")[-1] or term  # dotted path -> leaf symbol
            if len(term) < 4 or term.lower() in seen:
                continue
            seen.add(term.lower())
            idents.append(term)
        # Most signal first: prefer longer, then snake/camel over TitleCase words
        idents.sort(key=lambda t: (len(t), "_" in t), reverse=True)
        return idents[:limit]

    def _search_github(
        self, state: RunState, query: str
    ) -> list[dict[str, Any]]:
        """Run a code search, tracked against the budget."""
        self._check_budget(state)
        return self.github.search_code(query, per_page=10)

    def _read_and_parse_phase(
        self,
        state: RunState,
        owner: str,
        repo: str,
        candidates: list[dict[str, Any]],
    ) -> list[FileStructure]:
        """Read and AST-parse candidate files.

        Args:
            state: Current run state.
            owner: Repository owner.
            repo: Repository name.
            candidates: Search result items.

        Returns:
            List of parsed FileStructure objects.
        """
        file_structures: list[FileStructure] = []
        # Read the top ranked source candidates within budget. Five balances
        # recall (the real fix may span several files) against the LLM's
        # per-request token budget — more files means each gets less room.
        for item in candidates[:5]:
            path = item.get("path", "")

            self._check_budget(state)
            try:
                content = self.github.get_file(owner, repo, path)

                if path.endswith(".py"):
                    fs = self.ast.parse_python(content, path)
                else:
                    # Non-Python: skip AST, treat as raw text
                    fs = FileStructure(
                        path=path,
                        language="other",
                        raw_content=content[:4000],
                        truncated=len(content) > 4000,
                    )

                file_structures.append(fs)
            except Exception:
                continue

        return file_structures

    def _generate_phase(
        self,
        state: RunState,
        issue_text: str,
        file_structures: list[FileStructure],
        retry_context: str | None = None,
    ) -> tuple[str, str]:
        """Generate a patch using the LLM.

        Args:
            state: Current run state.
            issue_text: Bug description.
            file_structures: Parsed file structures.
            retry_context: Optional context for retry after failed validation.

        Returns:
            Tuple of (diff_text, rationale).
        """
        contexts = []
        for fs in file_structures:
            ctx = {
                "path": fs.path,
                "functions": [
                    {
                        "name": fn.name,
                        "lines": f"{fn.start_line}-{fn.end_line}",
                    }
                    for fn in fs.functions
                ],
                "classes": [
                    {
                        "name": cn.name,
                        "lines": f"{cn.start_line}-{cn.end_line}",
                    }
                    for cn in fs.classes
                ],
                "content": fs.raw_content,
            }
            contexts.append(ctx)

        prompt = issue_text
        if retry_context:
            prompt = retry_context + "\n\n" + prompt

        self._check_budget(state)
        return self.llm.generate_patch(prompt, contexts)

    def _check_budget(self, state: RunState) -> None:
        """Decrement and check the tool-call budget.

        Args:
            state: Current run state.

        Raises:
            BudgetExhaustedError: If budget reaches zero.
        """
        state.remaining_budget -= 1
        if state.remaining_budget < 0:
            raise BudgetExhaustedError(
                "Tool-call budget exhausted "
                f"(started with {state.request.tool_call_budget})"
            )

    def _insufficient_context(
        self,
        state: RunState,
        reason: str,
    ) -> RunResult:
        """Return an insufficient-context result.

        This is the designed stopping condition (PRD §6.5): the agent
        correctly determined it cannot proceed confidently. Distinct from
        _system_failure(), which means something broke unexpectedly.

        Args:
            state: Current run state.
            reason: Explanation of why we could not proceed.

        Returns:
            RunResult with failure status.
        """
        trace_path = self.trace_logger.write()
        sep = "=" * 60
        print()
        print(sep)
        print("COULD NOT GENERATE CONFIDENT PATCH")
        print(sep)
        print(f"Reason: {reason}")
        print(f"Trace saved to: {trace_path}")
        print(sep)
        return RunResult(
            status="insufficient_context",
            patch_path=None,
            trace_path=trace_path,
            rationale=None,
            reason=reason,
        )

    def _system_failure(
        self,
        state: RunState,
        reason: str,
    ) -> RunResult:
        """Return an error result for an unexpected, non-designed failure.

        Unlike _insufficient_context() (PRD §6.5's designed stopping
        condition), this path is reached only when an exception outside
        this project's typed error hierarchy (Rules.md §5) surfaces --
        i.e. something broke that the typed-error contract didn't
        anticipate, not a case where the agent correctly declined to
        guess. Kept as a visually distinct banner so it isn't confused
        with the designed insufficient-context path when scanning stdout
        or trace output.

        Args:
            state: Current run state.
            reason: Explanation of what went wrong.

        Returns:
            RunResult with status="error".
        """
        trace_path = self.trace_logger.write()
        sep = "!" * 60
        print()
        print(sep)
        print("RUN FAILED (UNEXPECTED ERROR)")
        print(sep)
        print(f"Reason: {reason}")
        print(f"Trace saved to: {trace_path}")
        print(sep)
        return RunResult(
            status="error",
            patch_path=None,
            trace_path=trace_path,
            rationale=None,
            reason=reason,
        )
