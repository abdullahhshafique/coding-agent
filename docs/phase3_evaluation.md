# Phase 3 — Evaluation & Metrics

**Date:** 2026-08-01 · **Dataset:** 16 real closed GitHub issues (click, jinja, werkzeug)
**Model under test:** `openai/gpt-oss-120b` (Groq). Ground truth: files changed in the merged PR that actually closed each issue.

---

## Headline metrics (PRD §4)

| Metric | Target (v1) | Measured | Notes |
|---|---|---|---|
| **Task completion rate** | ≥ 60% | **6.2%** (1/16) | Semantically correct patch vs the described bug |
| **Search precision** | ≥ 50% | **13%** avg | Files found vs files actually fixed |
| **Search recall** | ≥ 80% | **34%** avg | Real-fix files surfaced |
| **Loop failure rate** | < 10% | **0%** (0/16 hard errors) | No crashes / budget blowups |
| **Explainability** | 100% | **100%** of successful runs had a rationale | binary |
| **Avg tool calls / run** | trend line | **9.1** | search + read + 2×generate + validate |
| **Avg duration / run** | < 90 s | **32 s** | within target |

**Bottom line:** the loop is reliable (0% infra failure) but the *patch quality* is low. The bottleneck is not search or plumbing — it is the model producing a semantically-correct edit whose diff cleanly applies.

---

## Test set

Built by `scripts/build_test_set.py`: real *closed* issues (label `bug`), each
cross-referenced to a merged fixing PR; `expected_files` = that PR's changed
source files. 16 issues, deliberately a mix of trivial and vague/hard reports
(e.g. "help not resolving automatically") per the Phase 3 risk guidance.

Reproduce: `python run_evaluation.py` → `output/evaluation/per_case_results.json`.

---

## What the numbers reveal (failure-mode analysis)

Grouping the 16 runs by terminal reason:

| Outcome | Count | Root cause |
|---|---|---|
| `success`, **semantically correct** | 1 | right file, minimal diff applies and fixes intent |
| `success`, semantically **wrong** | 3 | diff is syntactically valid but solves the wrong thing / invents new APIs rather than editing the real fix site |
| `insufficient_context` — validation failed after retry | 9 | model's diff references code/lines that don't match the current file → lenient validator rejects (correctly) |
| `insufficient_context` — no files found | 3 | issue text names no symbol the code search lexically matches |

**Two structural findings:**
1. **Validator vs. model tension.** Making the validator strict enough to guarantee safety means it rejects diffs whose context lines the model didn't copy exactly; making it lenient enough to apply cares lets marginal (wrong) diffs through. Real answer: the *prompt/context* must carry enough exact code that a correct, copyable diff is the easy path — the AST-targeted context builder is the current attempt, and it moved task-completion from 0% → 6.2%.
2. **Recall of *the actual fix site* lags lexical search.** Even when the named class/function is surfaced (#3360, #3458), search recall is only 34% on the *full* expected-file set because fixes often touch adjacent files the issue never names.

**Value of the exercise:** the honest 6.2% / 34% replaces the "it looks like it works" demo impression with a real broken-point diagnosis. That is exactly what Phases.md says Phase 3 is for.

---

## Budget recommendation (P1)

Observed `avg_tool_calls ≈ 9`, max 14 of the default 20. **Keep the default budget at 20** — it is not the binding constraint; patch quality is.

---

## Limits of this evaluation (honest caveats)

- **Model:** scored with `gpt-oss-120b`, not the originally-chosen `llama-3.3-70b-versatile` (its 100k-token/day free quota was exhausted during iteration). Numbers are indicative, not a model comparison.
- **Semantic correctness** judged by reading each valid patch against the issue intent (PRD §4 allows human judgment); absolute exactness against the merged PR diff was not always obtainable.
- The 6.2% is **real, not rounded up** (PRD/Phases.md "no demos without numbers").

---

## Recommendations to raise the score (next iteration)

1. **Surgical-context generation:** show the *relevant function only* plus a small caller-callee window, not whole-file heads — reduces mistaken edits.
2. **Diff-shape contract via few-shot examples** in the system prompt: show one exact `@@ -N,M +N,M @@` mini-patch per call so the model clones the format.
3. **Validator feedback string** into the retry: currently we retry once with a generic error; feeding the precise mismatching line pair into the retry prompt would convert many validation failures into successes.
4. **Code-search fallback to a local clone+grep** when zero results (Open Q2's fallback is still unbuilt).
