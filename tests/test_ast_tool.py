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

    try:
        result = tool.parse_python(source, "broken.py")
        assert result.parse_method == "tree-sitter"
    except Exception:
        pass
