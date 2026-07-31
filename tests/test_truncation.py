# tests/test_truncation.py
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
    # The raw_content should have the truncation marker
    # and be roughly MAX_CONTENT_LINES + a few lines
    assert len(result.raw_content.splitlines()) <= MAX_CONTENT_LINES + 5


def test_small_file_not_truncated() -> None:
    """Test that small files are not truncated."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    source = "\n".join([f"x = {i}" for i in range(10)])

    result = tool.parse_python(source, "small.py")

    assert result.truncated is False
    assert "[truncated" not in result.raw_content


def test_file_exactly_at_limit_not_truncated() -> None:
    """Test that files at exactly MAX_CONTENT_LINES are not truncated."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    lines = [f"    x = {i}" for i in range(MAX_CONTENT_LINES)]
    source = "\n".join(lines)

    result = tool.parse_python(source, "exact.py")

    # Not truncated since it's not over the limit
    assert result.truncated is False
    assert "[truncated" not in result.raw_content


def test_truncated_content_still_parses() -> None:
    """Test that truncated content still parses correctly."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    # Create a source with many function definitions
    lines = []
    for i in range(MAX_CONTENT_LINES + 50):
        lines.append(f"def func_{i}():")
        lines.append(f"    return {i}")
    source = "\n".join(lines)

    result = tool.parse_python(source, "many_funcs.py")

    assert result.truncated is True
    # Functions should still be extracted from the truncated content
    # Note: The AST parse happens on the original source, not the truncated content
    # The truncation only affects the raw_content stored
    assert len(result.functions) > 0


def test_truncation_marker_appears_in_content() -> None:
    """Test that the truncation marker appears in raw_content."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    lines = [f"    x = {i}" for i in range(MAX_CONTENT_LINES + 10)]
    source = "\n".join(lines)

    result = tool.parse_python(source, "big.py")

    assert "[truncated:" in result.raw_content
    assert "lines omitted" in result.raw_content
