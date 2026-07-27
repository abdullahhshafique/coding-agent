# Rules.md — Coding Agent

**Status:** Draft v1 · **Last updated:** 2026-07-27

This document is binding for all code in this repo, whether written by hand or with AI assistance. Where a rule conflicts with convenience, the rule wins — this project exists partly to demonstrate disciplined engineering practice, not just a working demo.

---

## 1. Coding Standards

- **Formatter:** `black` (default config, no custom line-length overrides) — run automatically, never manually.
- **Linter:** `ruff` — must pass with zero warnings before any commit; no `# noqa` without a one-line comment explaining why.
- **Type checking:** `mypy` in strict mode. Every function has full type annotations — no bare `Any` except at the literal boundary of an external API response, and even then it must be immediately validated/coerced into a typed dataclass.
- **Naming conventions:**
  - `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for constants.
  - Tool wrapper classes are named `<Domain>Tool` (e.g. `GitHubTool`, `ASTTool`, `LLMTool`) — this naming convention is not cosmetic, it's how the orchestrator's uniform contract stays legible.
  - No abbreviations that aren't immediately obvious (`repo` is fine; `rslt` is not).
- **Max function length:** 40 lines (excluding docstring/blank lines). If a function grows past this, it's a signal to extract a helper — this is enforced by a `ruff` complexity rule, not just convention.
- **No global mutable state.** Every piece of run state lives inside the `RunState` object (Architecture.md §7) and is passed explicitly. If you're tempted to reach for a module-level variable to hold state across a run, that's the rule telling you the object model is wrong, not an exception to make.

---

## 2. Commit & Branching Convention

- **Commit format:** Conventional Commits — `<type>(<scope>): <description>`, e.g. `feat(github-tool): add search_code method`, `fix(ast-tool): handle tree-sitter fallback on syntax error`.
  - Types used: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- **Branch naming:** `feature/<short-name>`, `fix/<short-name>` — e.g. `feature/patch-validator`, `fix/budget-enforcement-off-by-one`.
- **No direct commits to `main`** — even solo, every change goes through a branch + PR, specifically because this project's own discipline is part of what it demonstrates. PR self-merge is fine; skipping the PR step is not.
- **Commit atomicity:** one logical change per commit — a commit that touches the GitHub Tool and unrelated formatting fixes across the whole repo is not acceptable; split it.

---

## 3. Documentation Standards

- **Docstrings:** every public function/class gets a docstring in Google style (Args/Returns/Raises) — this is the primary documentation surface, since there's no separate hosted docs site for a CLI tool.
- **Inline comments:** reserved for *why*, never *what* — a comment explaining "this is O(n) but n is bounded by the tool-call budget so it's fine" is good; a comment saying "loop over files" above a `for file in files:` line is noise and should be removed.
- **README:** must always reflect the actual current CLI invocation syntax — if a flag changes, the README changes in the same commit, not "later."
- **Architecture/PRD/Rules/Phases/design docs:** these five files are living documents. Any change that alters scope, a component's responsibility, or a decision recorded as "open" must update the relevant doc in the same PR as the code change — a PR that silently diverges from these docs is not reviewable.

---

## 4. Dependency Management

- **New dependencies require justification** in the PR description: what it does, why the stdlib or an existing dependency doesn't already cover it. No dependency added "just in case."
- **Exact versions pinned** in `requirements.txt` (no `^` or `~` ranges) — reproducibility matters more than always-latest for a project with no live users to push updates to.
- **License check:** any new dependency must be permissively licensed (MIT/Apache-2.0/BSD) — no GPL-family dependencies, to keep the repo's own license posture clean if it's ever made public as a portfolio piece.
- **Minimal surface:** prefer one well-established library over rolling a custom solution for solved problems (e.g. use `unidiff` for diff parsing rather than hand-rolling a diff parser) — but the reverse also holds: do not add a heavy framework (an agent framework, an orchestration library) where plain Python suffices, per Architecture.md's "no LangGraph here" principle.

---

## 5. Error Handling Patterns

- **Typed errors only.** Every tool (`GitHubTool`, `ASTTool`, `LLMTool`) raises a specific exception subclass (e.g. `GitHubRateLimitError`, `GitHubNotFoundError`, `ASTParseError`) — never a bare `Exception` or a raw `requests.HTTPError` bubbled up unhandled. The orchestrator must be able to distinguish failure types without string-matching an error message.
- **Never throw across a tool boundary uncaught.** Every tool wrapper catches its own external-call exceptions and re-raises as one of this project's typed errors — a raw `requests.ConnectionError` must never reach the orchestrator directly.
- **The orchestrator is the only place that decides "stop the run."** Individual tools report failure; they do not themselves decide to exit the process or print user-facing output.
- **Structured error logging:** every caught error is logged to the trace with: error type, the tool call it occurred during, and (redacted) input parameters — never a bare `print(e)`.
- **No silent `except: pass`.** Anywhere. If a failure is genuinely safe to ignore, catch the specific exception type and log why it's being ignored — an unqualified bare `except` is a rule violation regardless of intent.

---

## 6. Logging & Observability Rules

- **What to log:** every tool call (input, output summary, duration, success/failure) via the Trace Logger — this is the project's only observability surface, so it must be complete, not partial.
- **Levels:** `DEBUG` for per-tool-call detail, `INFO` for phase transitions (search → read → generate), `WARNING` for degraded paths (e.g. AST fallback triggered), `ERROR` for anything that ends the run.
- **No PII logging** — not expected to arise given this tool only processes public code and user-supplied bug text, but if a bug report happens to contain something like an email address or personal data, it is not to be echoed into the persisted trace file beyond what's minimally needed to reproduce the run; redact obvious patterns (email-like strings) before persisting.
- **API keys are never logged**, full stop — not even a prefix/suffix for "which key was used" debugging. If that's ever needed, log a static identifier set at config time, never a substring of the actual secret.
- **Minimum context per log line:** timestamp, run ID (a UUID generated per invocation), phase name, and either the tool name or "orchestrator" as the source.

---

## 7. Testing Rules

- **Coverage requirement:** every Tool class and the Orchestrator itself must have unit tests covering both the success path and at least one failure path (e.g. `GitHubTool` tests must include a 404 case and a rate-limit case, not just the happy path).
- **Test file naming:** `test_<module_name>.py`, mirroring the source module it tests.
- **Mocking policy:** mock only external I/O — GitHub API calls, Groq API calls, filesystem writes in the Output Writer. Never mock the Orchestrator's internal decision logic when testing the Orchestrator — that defeats the point of the test.
- **No test may make a real network call** except the explicitly-labeled contract tests (Architecture.md §11), which are excluded from the default `pytest` run and only invoked deliberately.

---

## 8. Accessibility Rules

Not applicable — this is a CLI tool with no graphical or web UI in v1. Noted here explicitly, per template, rather than omitted silently. If a future phase adds any UI surface (e.g. a simple web dashboard for viewing traces), accessibility rules (semantic HTML, ARIA, contrast, keyboard nav) will be added to this section at that time, matching whatever's specified in `design.md` then.

---

## 9. Performance Rules

- **No bundle size limits** — not applicable, no frontend bundle exists.
- **Tool-call budget is the primary performance guardrail** (Architecture.md §2/§7) — this replaces the usual "page load < 2s" style metric for a CLI/agent-loop project; the equivalent discipline here is bounding *external calls*, not bundle weight.
- **File truncation threshold:** any file over roughly 2,000 lines (or a token-count equivalent appropriate to the LLM context window) must be truncated around relevant AST nodes before being sent to the LLM Tool — never send an entire oversized file "just in case."
- **No premature optimization of the parsing layer** — correctness and clear fallback behavior (ast → tree-sitter → raw-text) matter more than parse speed in v1; the AST cache that would address repeated-parse cost is explicitly deferred (PRD US-13, P2), not something to informally half-build now.

---

## 10. Security Rules

- **Never store secrets in code.** `GITHUB_TOKEN` and `GROQ_API_KEY` are read exclusively from environment variables; `.env` is git-ignored; `.env.example` documents the required variable names with placeholder values only.
- **No CORS policy needed** — not applicable, no web-facing endpoint in v1.
- **API key rotation:** not automated in v1 (single local user); documented as a manual process in the README (regenerate the PAT/API key, update `.env`) — explicitly not a gap being silently ignored, just correctly scoped as out of v1's automation surface.
- **Read-only GitHub scope enforced at the token level**, not just by convention — the PAT requested/used should itself only carry public-repo read access; requesting broader scope "in case it's needed later" is a rule violation, not a convenience.

---

## 11. AI Assistance Boundaries

These rules govern what an AI assistant (Claude or otherwise) may and may not do when helping write this project's code — separate from what the *Coding Agent itself* does at runtime (that's the product; this section is about the development process building it).

- AI may suggest code, write tests, and draft documentation, **but every suggested change must include error handling** consistent with §5 above — a suggestion that adds a new tool call without a corresponding typed exception and trace-log entry is incomplete and must be revised before merging.
- AI **must not invent GitHub or Groq API endpoints, parameters, or response shapes.** If uncertain about an actual API's behavior, the AI must say so and prompt for verification against real documentation rather than presenting a plausible-sounding guess as fact.
- AI **must not modify `Rules.md`, `Architecture.md`, or `PRD.md` scope-defining sections without explicit human confirmation** — these documents represent decisions, not just descriptions, and an AI silently "improving" a scope boundary is a process violation even if the suggested change is reasonable on its own merits.
- AI **must not add auto-apply, auto-commit, or auto-PR functionality** without an explicit, separate decision to move US-10/US-11 from P2 into active scope — this boundary exists specifically because those are the actions with real-world write consequences, and "the agent could technically do this now" is not sufficient justification on its own.
- AI assistance in writing the Coding Agent's own prompts to the LLM Tool must preserve the "file content and issue text are data, not instructions" framing (Architecture.md §8) — an AI-suggested prompt rewrite that lets user/file content be interpreted as system-level instructions is a security regression, not a simplification.
- When AI-assisted code touches error handling, logging, or the tool-call budget enforcement, a human must explicitly review that specific diff before merge — these three areas are called out because they're where a plausible-looking but subtly wrong AI suggestion (e.g. a budget check with an off-by-one, or a caught exception that's actually too broad) is easiest to miss.

---

## 12. Code Review Checklist

Every PR — self-reviewed or otherwise — must confirm:

- [ ] All new external-call sites raise typed exceptions, not raw library exceptions (§5).
- [ ] Tool-call budget is decremented/checked at every actual external call site added (no new GitHub/Groq call bypasses the budget).
- [ ] No secrets, tokens, or raw API responses containing keys appear in logs, trace output, or test fixtures.
- [ ] Tests cover at least one failure path for any new external-call logic, not just the happy path.
- [ ] `black`, `ruff`, and `mypy --strict` all pass with zero warnings.
- [ ] Any scope or decision change is reflected in the relevant doc (PRD/Architecture/Rules/Phases) in the same PR.
- [ ] Commit messages follow Conventional Commits format.
- [ ] No function exceeds 40 lines without a documented reason.

---

## 13. Environment-Specific Behaviour

- **Feature flags:** none in v1 — a single code path, no conditional feature toggling. If a future phase needs to A/B a search strategy or model choice, flags will be introduced then, not speculatively now.
- **Debug mode:** a `--verbose` CLI flag raises the log level to `DEBUG` for the run (full per-tool-call detail printed to stderr in addition to the trace file) — this is the only environment-specific behavior in v1.
- **Mock data usage:** mock/fixture repos are used only inside the test suite (Architecture.md §11); the CLI tool itself never runs against mock data — every real invocation hits real GitHub and Groq APIs. There is no "demo mode" that fakes results, because a fake success would defeat the entire point of measuring the loop's real behavior.
