# PRD.md — Coding Agent

**Project:** Coding Agent (Project 1 of the Agentic Software House track)
**Owner:** Abdullah Shafique
**Status:** Draft v1
**Last updated:** 2026-07-27

---

## 1. Problem Statement & Context

### The pain
Fixing a bug or adding a small feature in an unfamiliar codebase follows a repetitive, mechanical loop: read the report, guess which files are relevant, grep around, open files, trace call sites, understand the surrounding logic, then write a change that fits the existing style and doesn't break anything nearby. This loop is slow specifically *because* it's manual — the search space (which files matter) and the read space (what those files actually do) both have to be rebuilt from scratch by a human, every time, even for small changes.

LLMs are good at the "generate a patch" step once they have the right context. They are bad at knowing *what the right context is* without being told. Most naive LLM coding demos skip this — they paste one file into a prompt and ask for a fix. That's not how real bug reports work: a report describes a symptom, not a file path.

### Why this, why now
This project exists as the **foundational exercise** before any multi-agent system is attempted. A multi-agent framework (the planned Agentic Software House, 16 specialist agents over LangGraph) is only as good as each individual agent's core loop: *prompt → tool call → result → repeat*. If that loop isn't solid — if the agent doesn't reliably decide *when* to search vs. read vs. generate, and doesn't handle tool failures or empty results gracefully — then stacking 16 of them in coordination will just multiply the failure modes.

Building a single-agent Coding Agent first, with no orchestration overhead, isolates that loop so it can be gotten right in isolation. It is also a legitimate standalone portfolio piece: it demonstrates real tool-use competency (GitHub API + AST parsing) that a "chat with your PDF" RAG demo does not.

### Why now (for the author)
Positioned as the next portfolio project after a recent audit flagged gaps including "no OpenAI-style function calling experience" and "no streaming implementation" in the existing project set. This project directly closes the function-calling / tool-orchestration gap.

---

## 2. Personas

> These personas are illustrative, written to sharpen requirements and test coverage. This is a solo portfolio/demo project — there are no real external users in v1. Personas are used the same way a solo indie developer uses "the imagined customer": to force concreteness in scope decisions.

### Persona 1 — "Dana, the maintainer triaging issues"
- **Goal:** Wants a fast, low-effort first pass on an incoming bug report before deciding whether to hand it to a human contributor.
- **Frustration:** Reports are often vague ("clicking export crashes sometimes") and pinpointing the relevant file takes longer than fixing the actual bug once found.
- **Context:** Comfortable reading diffs, not comfortable trusting an agent's patch without seeing its reasoning and the files it touched.

### Persona 2 — "Sam, the solo developer with a backlog"
- **Goal:** Wants to throw a feature request at a tool and get a draft patch to review and adapt, rather than starting from a blank file.
- **Frustration:** Context-switching into an unfamiliar part of their own codebase (a module they wrote six months ago) costs more time than the change itself.
- **Context:** Will accept an imperfect patch if it's clearly reasoned and easy to verify; will not accept a silent, unexplained change.

### Persona 3 — "Abdullah, evaluating the agent loop itself" (real user)
- **Goal:** Needs the CLI to expose its intermediate steps (which files it searched, what it read, why) so the *loop* can be debugged and improved, not just the final patch.
- **Frustration:** A black-box "here's your patch" tool is useless for learning whether the search → read → generate loop is actually working correctly.
- **Context:** Will read logs/traces closely; is the primary consumer of Success Metrics below in this v1.

---

## 3. User Stories / Use Cases

Priority key: **P0** = required for MVP demo, **P1** = required before calling v1 "done," **P2** = future phase.

| ID | Story | Priority |
|----|-------|----------|
| US-1 | As a maintainer, I want to give the agent a natural-language bug description and a repo URL, so that it finds the likely relevant files without me pointing it there. | P0 |
| US-2 | As a maintainer, I want the agent to show me *which* files it searched and *why* it picked them, so that I can trust or correct its reasoning. | P0 |
| US-3 | As a developer, I want the agent to parse the AST of candidate files, so that its understanding of "relevant code" is structural (functions, classes, call sites) rather than just keyword matches. | P0 |
| US-4 | As a developer, I want the agent to output a unified diff/patch, so that I can review it in a familiar format before applying it. | P0 |
| US-5 | As a developer, I want the agent to explain its patch in plain language, so that I can evaluate correctness without re-deriving the fix myself. | P1 |
| US-6 | As Abdullah, I want every tool call (GitHub search, file read, AST parse) logged with inputs/outputs, so that I can measure the loop's efficiency and debug failures. | P0 |
| US-7 | As a maintainer, I want the agent to tell me clearly when it *can't* find relevant files or is unsure, rather than guessing silently, so that I don't get a confidently wrong patch. | P0 |
| US-8 | As a developer, I want to run this against any public GitHub repo via a CLI flag, so that I'm not limited to one hardcoded test repo. | P1 |
| US-9 | As a developer, I want the agent to respect a maximum tool-call budget per run, so that a bad search loop can't burn API quota indefinitely. | P1 |
| US-10 | As a developer, I want to optionally auto-apply the patch to a local clone (still not committing/pushing), so that I can test it immediately. | P2 |
| US-11 | As a maintainer, I want the agent to open a draft PR with the patch, so that review happens where the team already works. | P2 |
| US-12 | As a developer, I want support for JS/TS repos in addition to Python, so that the tool isn't limited to one language. | P2 |
| US-13 | As a developer, I want a persistent cache of parsed ASTs per repo, so that repeated runs against the same repo are faster. | P2 |

---

## 4. Success Metrics / KPIs

Since this is a solo demo project, "success" is measured as **loop quality**, not user adoption:

- **Task completion rate:** % of test bug reports (from a curated set of ~15–20 real closed GitHub issues with known fixes) for which the agent's generated patch is *semantically correct* (judged manually against the real merged fix) — target ≥ 60% for v1, ≥ 75% by end of Phase 3.
- **Search precision:** Of the files the agent identifies as "relevant," what fraction were actually touched in the real fix — target ≥ 50% precision, ≥ 80% recall on the real fix's file set.
- **Tool-call efficiency:** Average number of tool calls per successful patch (lower is better, but not at the cost of accuracy) — track as a trend line, no hard target in v1.
- **Loop failure rate:** % of runs that error out, infinite-loop, or exceed the tool-call budget without producing any output — target < 10%.
- **Explainability:** 100% of generated patches must include a plain-language rationale (binary pass/fail per run, not a percentage).
- **Portfolio signal (soft metric):** Whether the finished project, demoed live against a real public repo, survives a "why did it pick that file?" follow-up question in an interview setting without hand-waving.

---

## 5. Scope & Out-of-Scope

### In scope (MVP / v1)
- Single agent, single Python process, CLI-invoked.
- GitHub API: read-only — search code, list files, fetch file contents, fetch issue/PR text if given a URL instead of raw text.
- AST parsing: Python only, via `ast` (stdlib) and `tree-sitter-python` for anything `ast` can't cleanly give (e.g. precise source-range mapping for diffs).
- Groq-hosted LLM for the reasoning/generation steps.
- Output: a unified diff (patch) printed to stdout and saved to a file, plus a plain-language rationale.
- Full trace/log of every tool call (search query, read, parse) for later analysis.
- Configurable tool-call budget per run (hard cap, enforced).
- Explicit "I don't have enough context to patch this confidently" output path — the agent must be allowed to fail loudly instead of guessing.

### Out of scope for v1 (future phases)
- Auto-committing, pushing, or opening PRs (US-10, US-11 — P2).
- Multi-language support beyond Python (US-12 — P2).
- Multi-agent coordination of any kind (that's the next project in the track, not this one).
- A GUI or web dashboard — CLI only.
- Persistent/shared AST cache across runs (US-13 — P2).
- Authentication flows beyond a single read-only GitHub PAT supplied via env var.
- Handling private repos requiring org-level permissions (a personal read-only PAT against a repo the user already has access to is sufficient).
- Fine-tuning any model — Groq's hosted models are used as-is.

---

## 6. Functional Requirements

### 6.1 Input handling
- Accepts: (a) a repo identifier (`owner/repo` or full GitHub URL), (b) a bug/feature description as raw text OR a GitHub issue URL to fetch the description from.
- **Validation:** repo identifier must resolve to a real, accessible public repo before any further work begins; if it 404s or is private without access, fail immediately with a clear message — do not silently proceed with a partial run.
- **Edge case:** if given both an issue URL and raw text, issue URL text takes precedence; raw text is treated as supplementary context, not primary.
- **Edge case:** empty or whitespace-only bug description → reject with an error before making any API calls.

### 6.2 Search phase
- Uses GitHub's code search API (and/or a local clone + grep/AST fallback if code search API is unavailable/rate-limited — see Assumptions) to surface candidate files based on keywords extracted from the bug description.
- Must log the exact search query used and the raw result count.
- **Edge case:** zero search results → the agent must retry with at least one reformulated query (e.g. broader keywords) before giving up; if still zero, output the "insufficient context" path (see 6.5), not a guess.
- **Edge case:** search returns too many results (e.g. > 50 candidate files) → must apply a ranking/filtering step (e.g. by keyword density, file type, path depth) rather than reading all of them — enforced by the tool-call budget regardless.

### 6.3 Read & AST parse phase
- For each candidate file (up to the budget), fetch full content, then parse via `ast`; if `ast` parsing fails (e.g. syntax error in a WIP branch, or the file isn't valid standalone Python — a template file, for instance), fall back to `tree-sitter-python`'s error-tolerant parsing rather than crashing the whole run.
- **Edge case:** a candidate file is not Python (e.g. a `.json` config file that matched a keyword) → skip AST parsing, treat as plain text context only, and log that it was downgraded.
- **Edge case:** a file exceeds a size threshold (e.g. very large generated file) → truncate intelligently around the most relevant AST nodes rather than sending the whole file to the LLM; log that truncation occurred.
- Structural output of this phase (function/class boundaries, call graph fragments) is passed to the generation phase as structured context, not just raw file text.

### 6.4 Generation phase
- LLM call includes: bug description, ranked candidate files with their relevant AST-derived structure, and an explicit instruction to output (a) a unified diff and (b) a plain-language rationale.
- **Validation:** the generated diff must be syntactically valid (parseable as a diff, and the resulting patched file must itself parse as valid Python) before being shown to the user. If it fails this check, the agent retries generation once with the parse error fed back in; if it fails twice, fall through to the insufficient-context path.
- **Edge case:** LLM proposes changes to a file that was never actually fetched/read in this run → reject and regenerate; the agent must not hallucinate a patch against unseen code.

### 6.5 Insufficient-context / failure path
- If search yields nothing usable, or generation can't produce a valid patch after retries, or the tool-call budget is exhausted first — the agent must output a clear, structured "could not generate a confident patch" result, including what it *did* try, rather than exiting silently or with a raw stack trace.

### 6.6 Output
- Unified diff written to `./output/<repo>-<timestamp>.patch` and printed to stdout.
- Rationale printed alongside it.
- Full tool-call trace written to `./output/<repo>-<timestamp>.trace.json`.

---

## 7. Non-Functional Requirements

- **Performance:** a single run (search → read → generate) should complete in under 90 seconds for a repo of typical portfolio-project size (< 500 files) under normal GitHub API latency and Groq inference latency. This is a target, not a hard SLA, given external API dependency.
- **Reliability:** the tool-call budget (default: 20 calls/run, configurable) must be a hard enforcement, not a soft guideline — the loop must check remaining budget before every tool call and stop cleanly when exhausted.
- **Security:** GitHub PAT and Groq API key are read from environment variables only, never from a config file committed to the repo, never logged in the trace output even in redacted partial form.
- **Rate-limit handling:** must detect GitHub API rate-limit responses (403/429) and fail with a clear, specific message distinguishing "rate limited, try again later" from "repo not found" or "auth failed" — these are different problems and must not share one generic error message.
- **Portability:** runs on a standard Python 3.11+ environment with dependencies pinned in `requirements.txt`; no OS-specific assumptions.
- **Accessibility / device support:** N/A — CLI tool, no UI surface in v1. (Explicitly noted as not applicable rather than skipped, per template.)
- **Scalability:** not a concern for v1 — single user, single run at a time, no concurrency requirements. Documented here explicitly so it isn't mistaken for an oversight.

---

## 8. User Flow Summary

1. User runs `coding-agent fix --repo owner/name --issue "<url or text>"`.
2. Agent validates repo + input → fails fast if invalid.
3. Agent searches repo for candidate files → logs query + results.
4. Agent reads + AST-parses top candidates within budget → logs each read/parse.
5. Agent generates patch + rationale → validates patch syntactically.
6. Agent writes patch, rationale, and trace to `./output/` and prints summary to stdout.
7. (Failure branch, any stage) → agent prints what was attempted and why it stopped, writes partial trace, exits non-zero.

A more detailed sequence diagram lives in `Architecture.md` §4 (Data Flow).

---

## 9. Assumptions & Dependencies

- **GitHub API:** assumes availability of the code search endpoint for the target repo; GitHub's code search API has known limitations (e.g. doesn't index all branches, has its own rate limits separate from the REST API). If code search proves unreliable in practice, the fallback is a shallow local clone + local grep/AST scan — this is a known risk, tracked in Architecture.md.
- **Groq API:** assumes continued availability and that the selected hosted model supports reliable structured/tool-call-style output. Model choice is an open question (see below).
- **GitHub PAT:** assumes the user supplies a personal access token with, at minimum, public repo read scope.
- **No regulatory constraints identified** — this tool processes public code and user-supplied text only; no PII handling by design.

---

## 10. Open Questions

| # | Question | Owner | Needed by |
|---|----------|-------|-----------|
| 1 | ~~Which specific Groq-hosted model...~~ **RESOLVED:** `llama-3.3-70b-versatile`, implemented in `LLMTool.MODEL`. Not benchmarked against a smaller/faster variant — chosen as a starting point. Revisit if Phase 3's tool-call-efficiency or task-completion numbers suggest a smaller model performs comparably at lower latency. | Abdullah | Resolved |
| 2 | Is GitHub's code search API sufficient, or does the fallback (shallow clone + local scan) need to be built as part of v1 rather than a later phase? | Abdullah | Before Phase 1 search-phase implementation |
| 3 | What's the actual curated test set of ~15–20 closed GitHub issues used to measure Task Completion Rate — which repos, how selected? | Abdullah | Before Phase 3 (evaluation) |
| 4 | ~~Should the tool-call budget be a single global cap, or split into sub-budgets per phase?~~ **RESOLVED:** single global cap, implemented in `RunState.remaining_budget` / `AgentOrchestrator._check_budget`. No per-phase sub-budgets in v1. | Abdullah | Resolved |

---

## 11. Glossary

- **Agent loop:** the repeating cycle of (prompt the LLM) → (LLM decides on/emits a tool call) → (execute tool call, get result) → (feed result back into the prompt) → repeat until a stopping condition.
- **AST (Abstract Syntax Tree):** a structural representation of source code, used here instead of raw text so the agent can reason about function/class boundaries and call sites rather than pattern-matching on text.
- **Tool-call budget:** a hard limit on the number of external tool invocations (search, read, parse) permitted in a single run, to bound cost and prevent runaway loops.
- **Insufficient-context path:** the explicit, designed failure mode where the agent reports it cannot confidently proceed, rather than guessing.
- **Unified diff / patch:** the standard `diff -u` style text format for representing a code change, applied via `git apply` or `patch`.
- **Tree-sitter:** an incremental parsing library used here as a fallback for error-tolerant AST parsing when Python's stdlib `ast` module fails (e.g. on non-standalone or syntactically incomplete files).
