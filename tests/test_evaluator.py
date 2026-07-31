# tests/test_evaluator.py
"""Tests for the evaluation framework."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coding_agent.evaluator import (
    EvalCase,
    EvaluationSummary,
    Evaluator,
    RunResult,
)


def test_compute_metrics_perfect_match() -> None:
    """Test precision=1.0, recall=1.0 when files match exactly."""
    evaluator = Evaluator()
    test = EvalCase(
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
        rationale="Fixed the bug",
        reason=None,
    )
    record = evaluator.compute_metrics(test, result, ["a.py", "b.py"], 5, 10.0)
    assert record.precision == 1.0
    assert record.recall == 1.0
    assert record.tool_calls_used == 5
    assert record.duration_seconds == 10.0
    assert record.files_found == ["a.py", "b.py"]


def test_compute_metrics_partial_match() -> None:
    """Test precision and recall with partial overlap."""
    evaluator = Evaluator()
    test = EvalCase(
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
        rationale="Fixed the bug",
        reason=None,
    )
    record = evaluator.compute_metrics(test, result, ["a.py", "d.py"], 5, 10.0)
    assert record.precision == 0.5  # 1/2
    assert abs(record.recall - (1 / 3)) < 0.001  # 1/3
    assert record.patch_correct is None  # Manual judgment required


def test_compute_metrics_no_files_found() -> None:
    """Test zero precision/recall when no files found."""
    evaluator = Evaluator()
    test = EvalCase(
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
    assert record.tool_calls_used == 3


def test_compute_metrics_with_extra_files() -> None:
    """Test precision/recall when agent finds extra files."""
    evaluator = Evaluator()
    test = EvalCase(
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
        rationale="Fixed the bug",
        reason=None,
    )
    record = evaluator.compute_metrics(test, result, ["a.py", "b.py", "c.py"], 5, 10.0)
    assert record.precision == 1 / 3  # 1/3
    assert record.recall == 1.0


def test_summarize_aggregates_correctly() -> None:
    """Test summary aggregation across multiple records."""
    evaluator = Evaluator()
    test = EvalCase(
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
        rationale="Fixed the bug",
        reason=None,
    )
    records = [
        evaluator.compute_metrics(test, result, ["a.py"], 5, 10.0),
        evaluator.compute_metrics(test, result, ["a.py", "b.py"], 3, 8.0),
    ]
    summary = evaluator.summarize(records)
    assert summary.total_cases == 2
    assert summary.avg_precision == 0.75  # (1.0 + 0.5) / 2
    assert summary.avg_recall == 1.0
    assert summary.avg_tool_calls == 4.0  # (5 + 3) / 2
    assert summary.avg_duration == 9.0  # (10 + 8) / 2


def test_summarize_handles_failures() -> None:
    """Test summary handles different status types."""
    evaluator = Evaluator()
    test = EvalCase(
        repo="x/y",
        issue_number=1,
        issue_url="",
        issue_title="",
        issue_body="",
        expected_files=["a.py"],
        description="",
    )
    success_result = RunResult(
        status="success",
        patch_path="/tmp/x.patch",
        trace_path="/tmp/x.trace.json",
        rationale="Fixed",
        reason=None,
    )
    insufficient_result = RunResult(
        status="insufficient_context",
        patch_path=None,
        trace_path="/tmp/x.trace.json",
        rationale=None,
        reason="No files found",
    )
    error_result = RunResult(
        status="error",
        patch_path=None,
        trace_path="/tmp/x.trace.json",
        rationale=None,
        reason="Unexpected error",
    )

    records = [
        evaluator.compute_metrics(test, success_result, ["a.py"], 5, 10.0),
        evaluator.compute_metrics(test, insufficient_result, [], 2, 3.0),
        evaluator.compute_metrics(test, error_result, [], 1, 1.0),
    ]
    summary = evaluator.summarize(records)

    assert summary.total_cases == 3
    assert summary.successful_patches == 1
    assert summary.failed_patches == 1
    assert summary.insufficient_context == 1


def test_write_summary_creates_file() -> None:
    """Test that write_summary creates a JSON file."""
    evaluator = Evaluator()
    summary = EvaluationSummary(
        total_cases=2,
        successful_patches=1,
        failed_patches=0,
        insufficient_context=1,
        avg_precision=0.75,
        avg_recall=1.0,
        avg_tool_calls=4.0,
        avg_duration=9.0,
        per_case=[
            {"case": 1, "status": "success"},
            {"case": 2, "status": "insufficient_context"},
        ],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        evaluator.output_dir = tmpdir
        path = evaluator.write_summary(summary)
        assert Path(path).exists()

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_cases"] == 2
        assert data["successful_patches"] == 1


def test_load_test_set_creates_cases() -> None:
    """Test that load_test_set creates EvalCase objects."""
    evaluator = Evaluator()

    test_data = [
        {
            "repo": "owner/repo",
            "issue_number": 1,
            "issue_url": "https://github.com/owner/repo/issues/1",
            "issue_title": "Bug title",
            "issue_body": "Bug description",
            "expected_files": ["src/module.py"],
            "description": "Fix the bug",
        }
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(test_data, f)
        temp_path = f.name

    try:
        cases = evaluator.load_test_set(temp_path)
        assert len(cases) == 1
        assert cases[0].repo == "owner/repo"
        assert cases[0].issue_number == 1
        assert cases[0].expected_files == ["src/module.py"]
    finally:
        Path(temp_path).unlink(missing_ok=True)
