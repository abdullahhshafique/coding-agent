# run_evaluation.py
"""Run the agent against the curated Phase 3 test set and save metrics.

Each case runs through the full search → read → generate → validate loop
against the live GitHub and Groq APIs. Results (per-case detail + aggregate
summary, with one final manual task-completion pass) are written to
./output/evaluation/ so docs/phase3_evaluation.md can be written from real,
reproducible numbers.

Re-runnable: cases that already produced a patch or a clean result are not
re-run unless --rerun is passed, so a partially-completed evaluation (rate
limits, crashes) can resume from where it stopped.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import time

# Load .env into the process env so GitHubTool / LLMTool find their keys when
# this runs directly. _env only sets variables not already in the real env.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from _env import load_env  # noqa: E402

load_env()

from coding_agent.evaluator import Evaluator  # noqa: E402
from coding_agent.models import RunRequest  # noqa: E402
from coding_agent.orchestrator import AgentOrchestrator  # noqa: E402

DETAIL_FILENAME = "per_case_results.json"


def _found_files(trace_records: list) -> list[str]:
    """Extract the repo-relative file paths the agent actually read."""
    files: list[str] = []
    for record in trace_records:
        if record.tool_name != "github":
            continue
        endpoint = record.input.get("endpoint", "")
        if "/contents/" in endpoint:
            path = endpoint.split("/contents/", 1)[1]
            if path not in files:
                files.append(path)
    return files


def main() -> None:
    evaluator = Evaluator()
    test_cases = evaluator.load_test_set("test_set.json")
    detail_path = os.path.join(evaluator.output_dir, DETAIL_FILENAME)

    # Load prior per-case detail so re-runs resume instead of starting over.
    prior: dict[str, dict] = {}
    if os.path.exists(detail_path) and "--rerun" not in sys.argv:
        try:
            for row in json.load(open(detail_path, encoding="utf-8")):
                prior[f"{row['repo']}#{row['issue_number']}"] = row
        except json.JSONDecodeError:
            prior = {}

    records = []

    for test in test_cases:
        key = f"{test.repo}#{test.issue_number}"
        if key in prior:
            row = prior[key]
            record = evaluator.compute_metrics(
                test,
                _result_from_row(row),
                row.get("files_found", []),
                row.get("tool_calls_used", 0),
                row.get("duration_seconds", 0.0),
            )
            # Preserve any manual patch-correctness judgment already recorded.
            record.patch_correct = row.get("patch_correct")
            records.append(record)
            print(f"SKIP  {key} (cached status={row['status']})")
            continue

        print(f"RUN   {key}: {test.issue_title[:60]}")
        start = time.perf_counter()
        orch = AgentOrchestrator()
        result = orch.run(
            RunRequest(
                repo=test.repo, issue_text=test.issue_body, tool_call_budget=20
            )
        )
        duration = time.perf_counter() - start

        files_found = _found_files(orch.trace_logger.records)
        record = evaluator.compute_metrics(
            test, result, files_found, len(orch.trace_logger.records), duration
        )
        records.append(record)
        print(
            f"      -> {result.status:20s} "
            f"precision={record.precision:.2f} recall={record.recall:.2f} "
            f"({duration:.0f}s)"
        )

        # Persist immediately so a crash/rate-limit keeps partial progress.
        _write_detail(records, detail_path)

    summary = evaluator.summarize(records)
    summary_path = evaluator.write_summary(summary)
    _write_detail(records, detail_path)

    print(f"\n{'=' * 58}")
    print("EVALUATION SUMMARY")
    print(f"{'=' * 58}")
    print(f"Total cases:          {summary.total_cases}")
    print(f"Successful patches:   {summary.successful_patches}")
    print(f"Insufficient context: {summary.insufficient_context}")
    print(f"Errors:               {summary.failed_patches}")
    print(f"Avg precision:        {summary.avg_precision:.2%}")
    print(f"Avg recall:           {summary.avg_recall:.2%}")
    print(f"Avg tool calls:       {summary.avg_tool_calls:.1f}")
    print(f"Avg duration:         {summary.avg_duration:.1f}s")
    print(f"{'=' * 58}")
    print(f"Per-case detail:  {detail_path}")
    print(f"Summary:          {summary_path}")
    print("\nNext: manually judge each patch for correctness, then edit")
    print(f"{detail_path} to set patch_correct per case.")


def _write_detail(records: list, detail_path: str) -> None:
    """Write per-case results to disk (called incrementally + at end)."""
    rows = []
    for r in records:
        tc = dataclasses.asdict(r.test_case)
        rows.append(
            {
                **tc,
                "status": r.run_result.status,
                "reason": r.run_result.reason,
                "patch_path": r.run_result.patch_path,
                "trace_path": r.run_result.trace_path,
                "rationale": r.run_result.rationale,
                "files_found": r.files_found,
                "precision": r.precision,
                "recall": r.recall,
                "tool_calls_used": r.tool_calls_used,
                "duration_seconds": round(r.duration_seconds, 1),
                "patch_correct": r.patch_correct,
            }
        )
    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def _result_from_row(row: dict):
    """Rebuild a minimal RunResult from a cached per-case detail row."""
    from coding_agent.models import RunResult

    return RunResult(
        status=row["status"],
        patch_path=row.get("patch_path"),
        trace_path=row.get("trace_path", ""),
        rationale=row.get("rationale"),
        reason=row.get("reason"),
    )


if __name__ == "__main__":
    main()
