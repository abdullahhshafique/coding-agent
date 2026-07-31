# tests/test_ast_tool.py
"""Tests for the AST tool."""

from __future__ import annotations

from unittest.mock import MagicMock

from coding_agent.ast_tool import ASTTool
from coding_agent.trace_logger import TraceLogger


def test_parse_python_simple_function() -> None:
    """Test parsing a simple function."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    source = """
def hello():
    print("world")
"""
    result = tool.parse_python(source, "test.py")

    assert result.path == "test.py"
    assert result.language == "python"
    assert len(result.functions) == 1
    assert result.functions[0].name == "hello"
    assert result.parse_method == "ast"


def test_parse_python_with_class() -> None:
    """Test parsing a class with methods."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    source = """
class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}"
"""
    result = tool.parse_python(source, "greeter.py")

    assert len(result.classes) == 1
    assert result.classes[0].name == "Greeter"
    assert len(result.functions) == 1
    assert result.functions[0].name == "greet"


def test_parse_python_invalid_syntax_fallback() -> None:
    """Test that invalid syntax triggers tree-sitter fallback."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    source = "def foo(:\n    pass"

    result = tool.parse_python(source, "broken.py")
    assert result.parse_method == "tree-sitter"


def test_parse_python_empty_file() -> None:
    """Test parsing an empty file."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    source = ""
    result = tool.parse_python(source, "empty.py")

    assert result.path == "empty.py"
    assert result.language == "python"
    assert len(result.functions) == 0
    assert len(result.classes) == 0
    assert result.parse_method == "ast"
    assert result.truncated is False


def test_parse_python_handles_tree_sitter_error() -> None:
    """Test that tree-sitter fallback handles errors gracefully."""
    trace = MagicMock(spec=TraceLogger)
    tool = ASTTool(trace)

    # A completely invalid file that even tree-sitter might struggle with
    source = "!!!!!@#$%^&*()"

    # This should still produce a result via tree-sitter's error-tolerant parsing
    result = tool.parse_python(source, "garbage.py")

    # tree-sitter should produce something, even if it's empty
    assert result.path == "garbage.py"
    assert result.language == "python"
    # parse_method might be tree-sitter if it succeeds, or fallback if not
    assert result.parse_method in ("tree-sitter", "raw-text-fallback")
    # tree-sitter can sometimes parse garbage as a series of error nodes
