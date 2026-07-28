"""Tests for data models."""

from __future__ import annotations

import datetime

from coding_agent.models import (
    ClassNode,
    FileStructure,
    FunctionNode,
    GenerationResult,
    RunRequest,
    RunResult,
    RunState,
    ToolCallRecord,
)


def test_run_request_defaults() -> None:
    """Test that RunRequest has expected defaults."""
    req = RunRequest(repo="owner/name")
    assert req.repo == "owner/name"
    assert req.issue_text is None
    assert req.issue_url is None
    assert req.tool_call_budget == 20


def test_run_state_tracks_budget() -> None:
    """Test that RunState initializes correctly."""
    req = RunRequest(repo="owner/name")
    state = RunState(request=req, remaining_budget=20)
    assert state.remaining_budget == 20
    assert state.trace == []
    assert state.candidates == []


def test_tool_call_record_creation() -> None:
    """Test that ToolCallRecord can be instantiated."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    record = ToolCallRecord(
        tool_name="github",
        input={"query": "test"},
        output=None,
        error=None,
        timestamp=now,
        duration_ms=100,
    )
    assert record.tool_name == "github"
    assert record.duration_ms == 100


def test_file_structure_defaults() -> None:
    """Test FileStructure default values."""
    struct = FileStructure(path="src/main.py", language="python")
    assert struct.functions == []
    assert struct.classes == []
    assert struct.parse_method == "ast"
    assert not struct.truncated
    assert struct.raw_content == ""


def test_generation_result_validity() -> None:
    """Test GenerationResult fields."""
    result = GenerationResult(
        diff_text="",
        rationale="test",
        files_touched=[],
        valid=False,
        validation_error="syntax error",
    )
    assert not result.valid
    assert result.validation_error == "syntax error"


def test_run_result_status() -> None:
    """Test RunResult creation."""
    result = RunResult(
        status="insufficient_context",
        patch_path=None,
        trace_path="/tmp/trace.json",
        rationale=None,
        reason="Not implemented",
    )
    assert result.status == "insufficient_context"
    assert result.patch_path is None


def test_function_node_creation() -> None:
    """Test FunctionNode instantiation."""
    node = FunctionNode(name="foo", start_line=1, end_line=5)
    assert node.name == "foo"
    assert node.start_line == 1


def test_class_node_creation() -> None:
    """Test ClassNode instantiation."""
    node = ClassNode(name="Bar", start_line=10, end_line=20)
    assert node.name == "Bar"
