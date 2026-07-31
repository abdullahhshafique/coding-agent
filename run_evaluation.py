# run_evaluation.py
"""Run evaluation against a curated test set."""

from __future__ import annotations

import time

from coding_agent.evaluator import Evaluator
from coding_agent.models import RunRequest
from coding_agent.orchestrator import AgentOrchestrator


def main() -> None:
    """Execute evaluation loop."""
    evaluator = Evaluator()
    test_cases = evaluator.load_test_set("test_set.json")
    records = []

    for test in test_cases:
        print(f"Evaluating: {test.repo}#{test.issue_number}")
        start = time.perf_counter()

        orch = AgentOrchestrator()
        request = RunRequest(
            repo=test.repo,
            issue_text=test.issue_body,
            tool_call_budget=20,
        )
        result = orch.run(request)
        duration = time.perf_counter() - start

        # Extract files found from trace records
        files_found: list[str] = []
        for record in orch.trace_logger.records:
            if record.tool_name == "github":
                endpoint = record.input.get("endpoint", "")
                if "/contents/" in endpoint:
                    path = endpoint.split("/contents/", 1)[1]
                    if path not in files_found:
                        files_found.append(path)

        record = evaluator.compute_metrics(
            test,
            result,
            files_found,
            len(orch.trace_logger.records),
            duration,
        )
        records.append(record)
        print(
            f"  Status: {result.status}, "
            f"Precision: {record.precision:.2f}, "
            f"Recall: {record.recall:.2f}"
        )

    summary = evaluator.summarize(records)
    path = evaluator.write_summary(summary)
    print(f"\nSummary written to: {path}")

    print(f"\n{'=' * 50}")
    print("EVALUATION SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total cases: {summary.total_cases}")
    print(f"Successful patches: {summary.successful_patches}")
    print(f"Insufficient context: {summary.insufficient_context}")
    print(f"Average precision: {summary.avg_precision:.2%}")
    print(f"Average recall: {summary.avg_recall:.2%}")
    print(f"Average tool calls: {summary.avg_tool_calls:.1f}")
    print(f"Average duration: {summary.avg_duration:.1f}s")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()