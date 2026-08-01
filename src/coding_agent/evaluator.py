"""Evaluation framework for measuring agent performance."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from coding_agent.models import RunResult


@dataclass
class EvalCase:
    """A single test case from a real GitHub issue."""

    repo: str
    issue_number: int
    issue_url: str
    issue_title: str
    issue_body: str
    expected_files: list[str]
    description: str


@dataclass
class EvaluationRecord:
    """Result of running the agent against one test case."""

    test_case: EvalCase
    run_result: RunResult
    patch_correct: bool | None
    files_found: list[str]
    precision: float
    recall: float
    tool_calls_used: int
    duration_seconds: float


@dataclass
class EvaluationSummary:
    """Aggregated metrics across all test cases."""

    total_cases: int
    successful_patches: int
    failed_patches: int
    insufficient_context: int
    avg_precision: float
    avg_recall: float
    avg_tool_calls: float
    avg_duration: float
    per_case: list[dict[str, Any]] = field(default_factory=list)


class Evaluator:
    """Runs the agent against a curated test set and computes metrics."""

    def __init__(self, output_dir: str = "./output/evaluation") -> None:
        """Initialize evaluator.

        Args:
            output_dir: Directory to write evaluation results.
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def load_test_set(self, path: str) -> list[EvalCase]:
        """Load test cases from a JSON file.

        Args:
            path: Path to JSON file containing test cases.

        Returns:
            List of EvalCase objects.
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [EvalCase(**item) for item in data]

    def compute_metrics(
        self,
        test_case: EvalCase,
        run_result: RunResult,
        files_found: list[str],
        tool_calls_used: int,
        duration_seconds: float,
    ) -> EvaluationRecord:
        """Compute precision, recall, and correctness for a single run.

        Args:
            test_case: The expected ground truth.
            run_result: The actual agent output.
            files_found: Files the agent identified as relevant.
            tool_calls_used: Number of tool calls consumed.
            duration_seconds: Wall-clock time of the run.

        Returns:
            EvaluationRecord with computed metrics.
        """
        expected = set(test_case.expected_files)
        found = set(files_found)

        true_positives = len(expected & found)
        precision = true_positives / len(found) if found else 0.0
        recall = true_positives / len(expected) if expected else 0.0

        # patch_correct stays None here: PRD §4 defines task-completion as
        # *semantic* correctness of the patch versus the real merged fix, which
        # requires human judgment, not an auto-check. run_evaluation.py leaves
        # it None and the scoring pass records the judgment afterward.
        patch_correct = None

        return EvaluationRecord(
            test_case=test_case,
            run_result=run_result,
            patch_correct=patch_correct,
            files_found=files_found,
            precision=precision,
            recall=recall,
            tool_calls_used=tool_calls_used,
            duration_seconds=duration_seconds,
        )

    def summarize(
        self,
        records: list[EvaluationRecord],
    ) -> EvaluationSummary:
        """Aggregate metrics across all evaluation records.

        Args:
            records: List of EvaluationRecord from each test case.

        Returns:
            EvaluationSummary with aggregated statistics.
        """
        total = len(records)
        successful = sum(1 for r in records if r.run_result.status == "success")
        failed = sum(1 for r in records if r.run_result.status == "error")
        insufficient = sum(
            1 for r in records if r.run_result.status == "insufficient_context"
        )

        avg_precision = sum(r.precision for r in records) / total if total else 0.0
        avg_recall = sum(r.recall for r in records) / total if total else 0.0
        avg_tool_calls = (
            sum(r.tool_calls_used for r in records) / total if total else 0.0
        )
        avg_duration = (
            sum(r.duration_seconds for r in records) / total if total else 0.0
        )

        per_case = []
        for r in records:
            per_case.append(
                {
                    "repo": r.test_case.repo,
                    "issue": r.test_case.issue_number,
                    "status": r.run_result.status,
                    "precision": r.precision,
                    "recall": r.recall,
                    "tool_calls": r.tool_calls_used,
                    "duration": r.duration_seconds,
                    "patch_correct": r.patch_correct,
                }
            )

        return EvaluationSummary(
            total_cases=total,
            successful_patches=successful,
            failed_patches=failed,
            insufficient_context=insufficient,
            avg_precision=avg_precision,
            avg_recall=avg_recall,
            avg_tool_calls=avg_tool_calls,
            avg_duration=avg_duration,
            per_case=per_case,
        )

    def write_summary(self, summary: EvaluationSummary) -> str:
        """Write evaluation summary to disk.

        Args:
            summary: The aggregated summary.

        Returns:
            Path to the written summary file.
        """
        path = os.path.join(self.output_dir, "evaluation_summary.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2)
        return path
