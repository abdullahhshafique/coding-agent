"""Tests for the evaluation framework."""

from __future__ import annotations

from coding_agent.evaluator import (
    Evaluator,
    RunResult,
    TestCase,
)


def test_compute_metrics_perfect_match() -> None:
    """Test precision=1.0, recall=1.0 when files match exactly."""
    evaluator = Evaluator()
    test = TestCase(
        repo="x/y",
        issue_number=1,
        issue_url="",
        issue_title="",
        issue_body="",
        expected_files=["a.py", "b.py"],
        description="",
    )
    result = RunResult(
        status="success",
        patch_path="/tmp/x.patch",
        trace_path="/tmp/x.trace.json",
        rationale="",
        reason=None,
    )
    record = evaluator.compute_metrics(test, result, ["a.py", "b.py"], 5, 10.0)
    assert record.precision == 1.0
    assert record.recall == 1.0


def test_compute_metrics_partial_match() -> None:
    """Test precision and recall with partial overlap."""
    evaluator = Evaluator()
    test = TestCase(
        repo="x/y",
        issue_number=1,
        issue_url="",
        issue_title="",
        issue_body="",
        expected_files=["a.py", "b.py", "c.py"],
        description="",
    )
    result = RunResult(
        status="success",
        patch_path="/tmp/x.patch",
        trace_path="/tmp/x.trace.json",
        rationale="",
        reason=None,
    )
    record = evaluator.compute_metrics(test, result, ["a.py", "d.py"], 5, 10.0)
    assert record.precision == 0.5  # 1/2
    assert record.recall == 1 / 3  # 1/3


def test_compute_metrics_no_files_found() -> None:
    """Test zero precision/recall when no files found."""
    evaluator = Evaluator()
    test = TestCase(
        repo="x/y",
        issue_number=1,
        issue_url="",
        issue_title="",
        issue_body="",
        expected_files=["a.py"],
        description="",
    )
    result = RunResult(
        status="insufficient_context",
        patch_path=None,
        trace_path="/tmp/x.trace.json",
        rationale=None,
        reason="No files found",
    )
    record = evaluator.compute_metrics(test, result, [], 3, 5.0)
    assert record.precision == 0.0
    assert record.recall == 0.0


def test_summarize_aggregates_correctly() -> None:
    """Test summary aggregation across multiple records."""
    evaluator = Evaluator()
    test = TestCase(
        repo="x/y",
        issue_number=1,
        issue_url="",
        issue_title="",
        issue_body="",
        expected_files=["a.py"],
        description="",
    )
    result = RunResult(
        status="success",
        patch_path="/tmp/x.patch",
        trace_path="/tmp/x.trace.json",
        rationale="",
        reason=None,
    )
    records = [
        evaluator.compute_metrics(test, result, ["a.py"], 5, 10.0),
        evaluator.compute_metrics(test, result, ["a.py"], 5, 10.0),
    ]
    summary = evaluator.summarize(records)
    assert summary.total_cases == 2
    assert summary.avg_precision == 1.0
    assert summary.avg_recall == 1.0
    assert summary.avg_tool_calls == 5.0
    assert summary.avg_duration == 10.0
