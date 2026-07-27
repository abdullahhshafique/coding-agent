# Architecture.md — Coding Agent

**Status:** Draft v1 · **Last updated:** 2026-07-27

---

## 1. High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Entry Point                        │
│                     coding-agent fix --repo ... --issue ...      │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      Agent Orchestrator    │◄──── enforces tool-call
                    │   (the core loop driver)   │       budget every step
                    └────────────┬──────────────┘
                                 │  prompt → tool call → result → repeat
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  GitHub Tool    │      │   AST Tool        │      │   LLM Tool        │
│  - search_code  │      │  - parse_python   │      │  - generate_patch │
│  - get_file     │      │  - extract_structure│    │  - explain_patch  │
│  - get_issue    │      │  (ast + tree-sitter│      │  (Groq API)       │
└───────┬─────────┘      │   fallback)        │      └────────┬──────────┘
        │                 └─────────┬──────────┘               │
        ▼                           ▼                           ▼
┌─────────────────┐        ┌─────────────────┐         ┌─────────────────┐
│  GitHub REST API  │        │  In-process       │         │   Groq API        │
│  (external)        │        │  parse (no ext.   │         │   (external)       │
│                     │        │  service)         │         │                     │
└─────────────────────┘        └─────────────────┘         └─────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     Patch Validator        │──── syntactic check,
                    │  (re-parse patched file)   │     retry-or-fail logic
                    └────────────┬──────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │      Output Writer         │──── .patch, rationale,
                    │  (./output/*.patch/.trace)  │     .trace.json
                    └─────────────────────────┘
```

Everything runs as a single local Python process. There is no server, no database, no queue. The only external services are the GitHub REST API and the Groq API.

---

## 2. Design Principles & Constraints

- **Single agent, no orchestration layer.** No LangGraph, no multi-agent state machine here — deliberately. The point of this project is to get the *loop itself* right before adding coordination overhead. (LangGraph is reserved for the later Agentic Software House project, which this one feeds patterns into.)
- **Tool-call budget enforced at the orchestrator, not the LLM.** The LLM is never trusted to self-limit; the orchestrator counts calls and hard-stops regardless of what the LLM "wants" to do next.
- **Fail loud, not silent.** Every phase has a defined failure output (see PRD §6.5). No phase is allowed to swallow an error and proceed with degraded/guessed state without logging that it did so.
- **Read-only against GitHub.** No write scope requested or used. This is a constraint, not just a v1 limitation — it removes an entire class of security concerns (accidental commits/pushes) from this phase of the project.
- **Structural context over raw text.** Wherever AST parsing succeeds, the LLM is given structured function/class boundaries, not just a wall of file text — this is the core hypothesis being tested by the project (does structural context measurably improve patch quality vs. naive text-dump).
- **API-contract driven internally.** Each tool (GitHub, AST, LLM) exposes a fixed, typed interface to the orchestrator (see §3) so that any tool can be swapped (e.g. GitHub → GitLab, Groq → another provider) without touching the orchestrator loop. This is the specific property that makes the architecture "extractable" for the later multi-agent project — each tool here is designed to later become one callable capability inside a specialist agent.
- **Explicitly not "serverless" or "offline-capable."** This is a local CLI tool with two hard external dependencies (GitHub, Groq). No offline mode is planned or claimed.

---

## 3. Component Breakdown

| Component | Responsibility | Interface (in/out) | Technology | Maintainer |
|---|---|---|---|---|
| **CLI Entry Point** | Parse args, validate input, invoke orchestrator, print final result | in: argv; out: exit code + stdout | Python `argparse` (or `click`) | Abdullah |
| **Agent Orchestrator** | Drives the loop: decides next tool call based on current state, enforces budget, detects stopping conditions | in: bug description + repo id; out: final result object (patch/rationale/trace or failure reason) | Plain Python, no framework | Abdullah |
| **GitHub Tool** | `search_code(query)`, `get_file(path)`, `get_issue(url)` — all read-only | in: query/path/url; out: typed result objects, raises typed errors on 404/403/429 | `requests` + GitHub REST API v3 | Abdullah |
| **AST Tool** | `parse_python(source)` → structural representation (functions, classes, call sites); falls back to tree-sitter on stdlib `ast` failure | in: raw source text; out: structured `FileStructure` object | Python stdlib `ast` + `tree-sitter` + `tree-sitter-python` | Abdullah |
| **LLM Tool** | `generate_patch(context)`, `explain_patch(diff)` — wraps Groq API calls | in: structured context object; out: raw diff text + rationale text | Groq Python SDK (or raw HTTP) | Abdullah |
| **Patch Validator** | Confirms the diff parses and the resulting patched file is valid Python | in: diff text + original file map; out: pass/fail + error detail | `ast` (re-parse check), a diff-parsing lib (e.g. `unidiff`) | Abdullah |
| **Output Writer** | Persists patch, rationale, and trace to disk in a consistent format | in: final result object; out: files on disk | Python stdlib `json`/file I/O | Abdullah |
| **Trace Logger** | Records every tool call (input, output, timestamp, duration) for later analysis | in: called from every tool wrapper; out: append to in-memory trace list, flushed at end | Plain Python | Abdullah |

> Single-maintainer project — "Maintainer" column exists to establish the pattern (a real multi-contributor project would need this column populated meaningfully) and to make clear this document's structure is itself a template for later, larger projects.

---

## 4. Data Model / Schema

No database. All state is in-memory for the duration of one run, plus files written at the end. The following are internal data shapes (Python dataclasses / TypedDicts), not persisted schemas:

```python
@dataclass
class RunRequest:
    repo: str                 # "owner/name"
    issue_text: str | None    # raw text, if given
    issue_url: str | None     # GitHub issue URL, if given
    tool_call_budget: int = 20

@dataclass
class ToolCallRecord:
    tool_name: str
    input: dict
    output: dict | None
    error: str | None
    timestamp: datetime
    duration_ms: int

@dataclass
class FileStructure:
    path: str
    language: str              # "python" | "other"
    functions: list[FunctionNode]
    classes: list[ClassNode]
    parse_method: str           # "ast" | "tree-sitter" | "raw-text-fallback"
    truncated: bool

@dataclass
class GenerationResult:
    diff_text: str
    rationale: str
    files_touched: list[str]
    valid: bool
    validation_error: str | None

@dataclass
class RunResult:
    status: str                # "success" | "insufficient_context" | "error"
    patch_path: str | None
    trace_path: str
    rationale: str | None
    reason: str | None         # populated on non-success
```

There is no ER diagram because there is no relational data store in v1. If a future phase adds the persistent AST cache (US-13, P2), that would introduce a real schema (likely SQLite: `repo`, `file_path`, `content_hash`, `parsed_structure_json`, `cached_at`) — deferred until that phase.

---

## 5. API Design

This project does not expose an API in v1 (CLI only, per PRD scope). This section documents the *external* APIs it consumes, since those are the actual integration surface:

### GitHub REST API (consumed)
- `GET /search/code?q=...` — code search within a repo. Auth: PAT via `Authorization: Bearer <token>` header. Rate limits apply per GitHub's documented tiers for authenticated search.
- `GET /repos/{owner}/{repo}/contents/{path}` — fetch file content.
- `GET /repos/{owner}/{repo}/issues/{number}` — fetch issue text, if an issue URL was given instead of raw text.
- No versioning strategy needed on our side — we consume GitHub's current stable REST API surface as-is.

### Groq API (consumed)
- `POST /openai/v1/chat/completions` (Groq's OpenAI-compatible endpoint) — used for both `generate_patch` and `explain_patch` calls. Auth via API key header.
- Model selection is an **open question** (see PRD §10, item 1).

### Internal "tool interface" contract
Even though there's no network API internally, each tool follows a consistent contract so the orchestrator never needs tool-specific branching logic:

```python
class Tool(Protocol):
    def call(self, **kwargs) -> ToolResult: ...
    # ToolResult always has: .success, .data, .error, .metadata
```

This uniform contract is the piece explicitly designed to survive into the later multi-agent project — each specialist agent there will wrap similar tool contracts.

---

## 6. Data Flow — Critical Path

The one critical path in this system is the full run, end to end:

```
1. CLI parses args
        │
2. Orchestrator validates repo exists + is accessible
        │  (GitHub Tool: a lightweight GET to /repos/{owner}/{repo})
        │  ── fails here → exit non-zero, no further calls made
        ▼
3. Orchestrator resolves issue text
        │  (GitHub Tool: get_issue, if URL given)
        ▼
4. LOOP START — Search phase
        │  Orchestrator asks LLM Tool: "what keywords should I search for?"
        │  Orchestrator calls GitHub Tool: search_code(keywords)
        │  ── budget decremented; if zero results, reformulate once, retry
        │  ── if still zero → status = insufficient_context, STOP
        ▼
5. Read + Parse phase
        │  For each candidate (within remaining budget):
        │    GitHub Tool: get_file(path)
        │    AST Tool: parse_python(content)  [fallback to tree-sitter on failure]
        │  ── budget decremented per file read
        ▼
6. Generation phase
        │  LLM Tool: generate_patch(bug_text + structured file contexts)
        │  Patch Validator: check diff parses + patched file is valid Python
        │  ── invalid → retry generation once with error fed back
        │  ── invalid twice → status = insufficient_context, STOP
        ▼
7. Explain phase
        │  LLM Tool: explain_patch(diff)
        ▼
8. Output Writer
        │  writes .patch, prints rationale, writes .trace.json
        ▼
9. LOOP END — exit 0 (success) or non-zero (insufficient_context / error)
```

There is no login flow, no payment flow, no data sync flow in this project — those are not applicable here and are omitted rather than stubbed out.

---

## 7. State Management Strategy

- **No frontend** — not applicable.
- **Backend/process state:** all state lives in a single `RunState` object owned by the Agent Orchestrator, passed through the loop by reference, never as global/module-level mutable state. This is a deliberate constraint: it keeps the orchestrator testable in isolation and mirrors how state would be scoped per-agent in the later multi-agent system.
- **No caching in v1** — every run re-fetches and re-parses from scratch. This is a known, accepted cost for v1 (see Technical Risks below); the AST cache is explicitly deferred (US-13, P2).
- **No sessions** — each CLI invocation is a fully independent run with no persisted state between invocations.

---

## 8. Security Architecture

- **Threat model (scoped to what's realistic for this tool):**
  - Leaking the GitHub PAT or Groq API key via logs, trace files, or error messages → **mitigation:** both are read from environment variables only; the Trace Logger explicitly redacts any string matching known key patterns before writing to `.trace.json`; keys are never included in prompts sent to the LLM.
  - A malicious or malformed repo causing the parser to hang or crash → **mitigation:** file size threshold before parsing (PRD §6.3); parse operations run with a timeout; a single file's parse failure must not crash the whole run (fallback to tree-sitter, then to raw-text-fallback, then to skipping that file entirely).
  - Prompt injection via file content or issue text (e.g. a file containing text designed to manipulate the LLM into ignoring its patch-generation instructions) → **mitigation:** the system prompt to the LLM Tool explicitly frames file content and issue text as *data*, not *instructions*; the orchestrator does not execute anything the LLM "asks" to do outside its defined tool contract (there is no dynamic tool the LLM can invent).
  - Generated patch containing something harmful if blindly applied (this is why auto-apply is P2/out of scope for v1) → **mitigation:** v1 never applies the patch automatically; it is always output for human review only.
- **Encryption:** not applicable to data at rest (no persisted user data); all external calls (GitHub, Groq) are over HTTPS, so encryption in transit is inherited from those APIs.
- **RBAC:** not applicable — single local user, single PAT, no multi-user access model in v1.
- **CSP / input sanitization:** not applicable in the browser sense (no web surface); the closest analog — sanitizing file content and issue text before including in prompts — is handled by the "framed as data, not instructions" mitigation above.

---

## 9. Deployment & Infrastructure

- **Hosting:** none required — this is a local CLI tool, distributed as a Python package (installable via `pip install -e .` in v1; PyPI publish is a future consideration, not v1 scope).
- **CI/CD:** GitHub Actions running on every push — lint (`ruff`), type-check (`mypy`), and run the test suite (§11). No deployment step exists yet since there's nothing to deploy to; CI's job in v1 is purely correctness gatekeeping.
- **Containerization:** not required for v1 (single-user local CLI); a `Dockerfile` may be added later purely for reproducibility of the demo, not as a runtime requirement.
- **Environment strategy:** a single `.env.example` documents required variables (`GITHUB_TOKEN`, `GROQ_API_KEY`); no staging/prod distinction exists for a local CLI tool — this is explicitly noted as not applicable rather than glossed over.

---

## 10. Error Handling & Resilience

- **Retry logic:** exactly one retry is permitted at two specific points — search query reformulation (PRD §6.2) and patch regeneration after a validation failure (PRD §6.4). No retries elsewhere; unbounded retry is explicitly avoided as a design choice, not an oversight.
- **Circuit breaker:** not implemented as a formal pattern in v1 — the tool-call budget serves the same practical purpose (bounding total external calls) for a single-run CLI tool. A true circuit breaker (tracking failure rates across many runs) is deferred until this becomes a long-running service, which it isn't.
- **Graceful degradation:** AST parse failure degrades to tree-sitter, then to raw-text-fallback, then to skipping the file — never a hard crash for one bad file.
- **Logging/monitoring:** structured JSON trace per run (§4, Trace Logger); no centralized monitoring/alerting infrastructure — not applicable for a local single-user CLI tool run on demand.

---

## 11. Testing Strategy

- **Unit tests:** each Tool (GitHub, AST, LLM, Validator) tested in isolation with mocked external calls — no real network calls in unit tests, ever.
- **Integration tests:** the full orchestrator loop tested against a small set of fixture repos (checked into the test suite as local fixtures, not live GitHub calls) to verify the search → read → generate sequence behaves correctly end to end without hitting real external APIs.
- **Contract tests:** a small set of tests that hit the *real* GitHub and Groq APIs (rate-limited, run manually or on a schedule rather than every CI push) to catch drift if either external API's response shape changes.
- **E2E / manual evaluation:** the curated set of ~15–20 real closed GitHub issues (PRD §4, Open Question #3) is run manually, not as part of automated CI, since "is this patch semantically correct" requires human judgment in v1.
- Test files follow `test_<module>.py`; mocking policy: mock only external I/O (GitHub API, Groq API, filesystem where relevant) — never mock internal orchestrator logic under test.

---

## 12. Technical Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| GitHub code search API has known indexing limitations (doesn't cover all branches, sometimes lags on recently pushed content) | Search phase returns poor candidates even when a good file exists | Fallback path: shallow local clone + local grep/AST scan, flagged as an open question (PRD §10, item 2) to decide if this is built in v1 or deferred |
| No persistent AST cache means repeated runs against the same repo re-do all parsing work | Slower iteration during development/demo | Accepted cost for v1; US-13 (P2) tracks the eventual fix |
| Groq model selection unresolved — a model good at chat may not be reliably good at emitting valid diffs | Generation phase produces frequently-invalid patches, burning the retry budget | Patch Validator's re-parse check catches this before it reaches the user; model choice is an explicit open question to resolve early in Phase 1, not discovered late |
| Prompt injection via adversarial file/issue content | Could cause the LLM to ignore instructions or emit unexpected output | Mitigated at the prompt-framing level (§8); this is a single point of trust that should be revisited if this pattern is reused in the multi-agent project, where the blast radius of a compromised agent is larger |
| Single point of failure: the whole run is one process, one loop | Any unhandled exception kills the entire run with no partial output | Trace Logger writes incrementally (not just at the end) specifically so a crash still leaves a partial trace on disk for debugging |

---

## 13. Migration Path / Backward Compatibility

Not applicable — this is a greenfield project with no existing system being replaced.
