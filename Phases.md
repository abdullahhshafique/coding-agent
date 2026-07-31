# Phases.md — Coding Agent

**Status:** Draft v1 · **Last updated:** 2026-07-27
**Timeline note:** open-ended, no hard deadline. Milestones below are sequencing markers, not calendar commitments — this is a solo project with flexible pacing.

---

## Phase 0 — Setup & Skeleton

**Objective:** Get a runnable, empty-but-correct skeleton in place before any real logic is written, so every later phase is additive rather than restructuring.

### Epics / features
| Feature | Priority |
|---|---|
| Repo scaffolding (package structure, `requirements.txt`, `.env.example`, `.gitignore`) | P0 |
| CLI entry point that parses args and prints "not yet implemented" | P0 |
| `RunState`, `RunRequest`, `ToolCallRecord`, `RunResult` dataclasses defined per Architecture.md §4 | P0 |
| CI pipeline: lint + type-check running on every push (test step added once tests exist) | P0 |
| Base exception hierarchy (`GitHubRateLimitError`, `ASTParseError`, etc. per Rules.md §5) | P0 |

### Definition of Done
- `pip install -e .` works from a clean environment.
- `coding-agent fix --repo x/y --issue "..."` runs and exits cleanly with a "not implemented" message — no crash.
- CI passes (lint + type-check) on the initial commit.
- All five governing docs (this one included) exist and are checked into the repo.

### Timeline & Milestones
- No fixed dates. Milestone: "skeleton runs end-to-end with stub logic" — target this before starting Phase 1.

### Dependencies
- None (first phase).

### Risks & Mitigation
- **Risk:** over-engineering the skeleton (adding structure for features not yet needed). **Mitigation:** if a dataclass field or module isn't used by the end of Phase 1, remove it rather than leaving speculative structure in place.

### Resources
- Solo — Abdullah, all roles.

### Deliverables
- Runnable skeleton repo, CI green, governing docs committed.

### Exit Criteria
- Skeleton runs without error against a real (if unimplemented) CLI invocation. Proceed to Phase 1.

---

## Phase 1 — Core Agent Loop (Search → Read → Generate, Happy Path Only)

**Objective:** Get the full happy-path loop working end to end against one known-good test repo, with no error handling depth yet — prove the shape of the loop before hardening it.

### Epics / features
| Feature | Priority |
|---|---|
| `GitHubTool.search_code`, `.get_file`, `.get_issue` — happy path only | P0 |
| `ASTTool.parse_python` using stdlib `ast` — happy path only | P0 |
| `LLMTool.generate_patch`, `.explain_patch` — Groq integration, model chosen per Open Question #1 | P0 |
| Agent Orchestrator driving the loop end to end, budget-tracked | P0 |
| Output Writer producing `.patch`, rationale, `.trace.json` | P0 |
| Decision: GitHub code search vs. local clone fallback (Open Question #2) — resolved before this phase's search feature is built | P0 |

### Definition of Done
- A full run against one hand-picked, simple, real GitHub repo + a known bug produces *a* patch (not necessarily correct yet) with no crash.
- Trace file correctly logs every tool call made during that run.
- Groq model choice is finalized and documented (Open Question #1 closed).
- Unit tests exist for the happy path of every Tool class.

### Timeline & Milestones
- Milestone: "first end-to-end patch generated against a real repo." No fixed date.
- Informal review checkpoint: demo the full loop to self (or a peer, if available) before moving to Phase 2.

### Dependencies
- Phase 0 skeleton complete.
- Open Questions #1 and #2 (PRD §10) resolved — these block real implementation, not just documentation.

### Risks & Mitigation
- **Risk:** GitHub code search API proves unreliable for the test repo (known limitation, Architecture.md §12). **Mitigation:** if hit early, pivot to the local-clone fallback immediately rather than working around it superficially — this is exactly why Open Question #2 is gated to before this phase starts.
- **Risk:** Groq model output isn't reliably diff-shaped. **Mitigation:** budget time in this phase specifically for prompt iteration on the generation step; if one model underperforms, the model choice is not treated as final until this phase validates it.

### Resources
- Solo — Abdulland, all roles.

### Deliverables
- Working end-to-end loop (uncertain quality, but functional), first real trace files as evidence.

### Exit Criteria (Go/No-Go)
- **Go:** a full run completes without crashing and produces a plausible (even if imperfect) patch. **No-Go / pause condition:** if neither GitHub search nor the local-clone fallback can reliably surface relevant files after real attempts, stop and reassess the search strategy before continuing — don't proceed to hardening a broken search phase.

---

## Phase 2 — Error Handling, Budget Enforcement & Fallback Paths

**Objective:** Harden the loop built in Phase 1 — every edge case named in PRD §6 gets a real, tested implementation, not just a mention in a doc.

### Epics / features
| Feature | Priority |
|---|---|
| Full typed exception hierarchy wired through every Tool (Rules.md §5) | P0 |
| Tool-call budget hard enforcement + tests proving it stops a run correctly | P0 |
| tree-sitter fallback for AST parse failures | P0 |
| Insufficient-context failure path (PRD §6.5) implemented and tested | P0 |
| Patch Validator with retry-once-then-fail logic | P0 |
| Rate-limit-specific error messages (distinguishing rate-limited / not-found / auth-failed) | P1 |
| File truncation for oversized files | P1 |

### Definition of Done
- Every edge case listed in PRD §6 has a corresponding automated test.
- A deliberately-broken/rate-limited scenario is manually tested and produces the correct specific error message, not a generic failure.
- All P0 items above complete; P1 items complete or explicitly deferred with a documented reason.

### Timeline & Milestones
- Milestone: "loop survives deliberate abuse" — try feeding it a nonexistent repo, an empty issue, a massive file, an intentionally rate-limited scenario, and confirm each fails the *right* way.

### Dependencies
- Phase 1's happy-path loop must be working first — you can't harden a loop that doesn't yet do the thing.

### Risks & Mitigation
- **Risk:** edge case handling is added ad hoc without the typed-exception discipline from Rules.md, creating inconsistent error shapes. **Mitigation:** code review checklist (Rules.md §12) is applied strictly starting this phase, even solo — self-review against the checklist before merging each PR.

### Resources
- Solo — Abdullah.

### Deliverables
- Hardened loop, edge-case test suite, updated trace format if needed to capture new failure metadata.

### Exit Criteria
- All P0 edge cases handled and tested. Proceed to Phase 3.

---

## Phase 3 — Evaluation & Metrics

**Objective:** Actually measure the Success Metrics defined in PRD §4 against a real, curated test set — this is where "does the loop work" gets an honest, numeric answer instead of a demo-day impression.

### Epics / features
| Feature | Priority |
|---|---|
| Curate the ~15–20 closed GitHub issue test set (Open Question #3, resolved here) | P0 |
| Run the agent against the full test set, capture all traces | P0 |
| Manual scoring: task completion rate, search precision/recall (PRD §4) | P0 |
| Write up results (what worked, what didn't) — feeds directly into Phase Retrospective Log below | P0 |
| Tune tool-call budget defaults based on observed average usage | P1 |

### Definition of Done
- Test set selected and documented (which repos, which issues, why chosen).
- Every metric in PRD §4 has an actual measured number, not a target.
- A written summary exists of failure modes observed (e.g. "search precision is low on repos with generic function names").

### Timeline & Milestones
- Milestone: "first honest scorecard" — this is the point where the project either validates its own premise (structural AST context improves patch quality) or reveals it doesn't, and that finding is reported honestly either way.

### Dependencies
- Phase 2's hardened loop, since a fragile loop would contaminate the evaluation with infrastructure failures rather than genuine quality signal.

### Risks & Mitigation
- **Risk:** test set is too small or cherry-picked to be meaningful. **Mitigation:** deliberately include at least a few issues expected to be *hard* (vague descriptions, larger repos) alongside easy ones — a test set that only contains easy wins isn't measuring anything useful.

### Resources
- Solo — Abdullah.

### Deliverables
- Test set (documented), full trace logs for every run, written evaluation summary with real numbers.

### Exit Criteria
- Metrics recorded, summary written. This is also the natural point to decide whether to continue into P2 features (multi-language, auto-apply) or consider v1 "done" and move to the next project in the track.

---

## Phase 4 — Polish, Documentation & Portfolio Packaging

**Objective:** Make the project presentable as a portfolio artifact — this phase exists because the project's purpose includes demonstrating engineering competency to an outside reviewer, not just working correctly.

### Epics / features
| Feature | Priority |
|---|---|
| README rewrite: clear setup instructions, example invocation, example output | P0 |
| Record/write up the Phase 3 evaluation results in a reviewer-friendly format | P0 |
| Clean up any dead code / stub paths left from earlier phases | P0 |
| GitHub repo public-facing polish (description, topics, pinned if applicable) | P0 |
| LinkedIn post announcing the project, referencing the real metrics from Phase 3 | P1 |
| Short demo (asciinema recording or similar) of a real run | P1 |

### Definition of Done
- A stranger could clone the repo, follow the README, and successfully run it against a repo of their choice within a few minutes.
- No "no demos without numbers" violations — every claim made publicly about this project is backed by a Phase 3 metric, not a vibe.

### Timeline & Milestones
- Milestone: "ready to link from portfolio/CV/interview conversation."

### Dependencies
- Phase 3 metrics must exist before public claims are made about the project's performance.

### Risks & Mitigation
- **Risk:** overstating results in public-facing copy relative to what Phase 3 actually measured. **Mitigation:** every public claim is checked against the Phase 3 written summary before publishing — no rounding a 60% completion rate up to "reliably" anything.

### Resources
- Solo — Abdullah.

### Deliverables
- Polished README, public GitHub repo, LinkedIn post (if pursued), optional demo recording.

### Exit Criteria
- Project is publicly linkable and its claims are accurate. This closes v1 of the Coding Agent project.

---

## Deploying on GitHub and LinkedIn

- **GitHub:** repo made public at end of Phase 4, not before — an in-progress repo with placeholder text live in production was previously flagged as a hireability issue; this project is deliberately not made public until it has real, accurate content throughout (README, code, and this documentation set).
- **LinkedIn:** a single post at the end of Phase 4, framed around the real Phase 3 metrics ("built X, measured Y% completion rate on a real test set of closed issues") rather than a generic "check out my new project" post — consistent with the "no demos without numbers" principle already in practice across other projects.
- Both deployment steps are gated on Phase 3 metrics existing first — this is a hard sequencing rule, not a suggestion.

---

## Phase Retrospective Log

> Placeholder — to be filled in after each phase actually completes. Format: what went well, what didn't, what would be done differently.

### Phase 0 Retrospective
*(not yet completed)*

### Phase 1 Retrospective

**Went well:** the loop's shape — search → read → generate → validate — proved
correct on the first working end-to-end run. Choosing `llama-3.3-70b-versatile`
early and pinning it removed a whole class of "which model" churn during
prompt iteration. Keeping the agent framework-free (plain Python, no
LangGraph) kept the loop debuggable; every failure could be traced to a single
tool call in the trace log.

**Didn't go well:** the Groq SDK pin (0.9.0) silently broke against the
installed `httpx` 0.28 (`proxies` kwarg removed). This wasn't caught until
Phase 3 because no test actually constructed a real `Groq` client — every test
mocked it. A pinning/compat test (or a contract test that hits the real
client constructor) would have caught it immediately.

**Would do differently:** add one real-client-construction smoke test per
external SDK in Phase 1, so "the dependency upgraded under us" is a build
failure, not a Phase 3 surprise.

### Phase 2 Retrospective

**Went well:** the typed-error hierarchy (Rules.md §5) paid off exactly as
designed — every tool failure routes cleanly to the insufficient-context
path, and the budget enforcement was testable in isolation. The
tree-sitter fallback meant a single unparseable file never crashed a run.

**Didn't go well:** the first PatchValidator leaned on `unidiff`, whose strict
hunk-header parsing rejects the *majority* of real LLM diffs (models rarely
emit exact `@@ -a,b +c,d @@` counts) — so validator tests were passing while
the component would have failed live. The fix required a hand-rolled
lenient-parser / strict-applier: lenient about *locating* a hunk, strict about
*applying* it so a fuzzy diff can't silently delete unmentioned code. That
lenient-parse/strict-apply split should have been the original design.

**Would do differently:** test validator components against *actual model
output* (captured diffs), not hand-written canonical diffs, from the first
iteration — the gap between "diff that textbooks produce" and "diff an LLM
produces" is where the real work was.

### Phase 3 Retrospective
*(not yet completed)*

### Phase 4 Retrospective
*(not yet completed)*
