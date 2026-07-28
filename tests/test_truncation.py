"""Tests for file truncation."""

from __future__ import annotations

from unittest.mock import MagicMock

from coding_agent.ast_tool import MAX_CONTENT_LINES, ASTTool
from coding_agent.trace_logger import TraceLogger


def test_large_file_gets_truncated() -> None:
    """Test that files over MAX_CONTENT_LINES are truncated."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    # Create a source with more than MAX_CONTENT_LINES lines
    lines = [f"    x = {i}" for i in range(MAX_CONTENT_LINES + 100)]
    source = "\n".join(lines)

    result = tool.parse_python(source, "big.py")

    assert result.truncated is True
    assert "[truncated" in result.raw_content
    assert len(result.raw_content.splitlines()) <= MAX_CONTENT_LINES + 5


def test_small_file_not_truncated() -> None:
    """Test that small files are not truncated."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    source = "\n".join([f"x = {i}" for i in range(10)])

    result = tool.parse_python(source, "small.py")

    assert result.truncated is False
    assert "[truncated" not in result.raw_content
