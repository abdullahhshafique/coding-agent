# tests/test_llm_tool.py
"""Tests for the LLM tool."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from coding_agent.exceptions import LLMError
from coding_agent.llm_tool import _FENCE_RE, LLMTool
from coding_agent.trace_logger import TraceLogger


@pytest.fixture
def llm_tool() -> LLMTool:
    """Create an LLMTool with a mock trace logger."""
    trace = MagicMock(spec=TraceLogger)
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test1234567890"}):
        return LLMTool(trace)


def test_llm_tool_requires_api_key() -> None:
    """Test that LLMTool raises without API key."""
    trace = MagicMock(spec=TraceLogger)
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(LLMError) as exc_info:
            LLMTool(trace)
        assert "GROQ_API_KEY" in str(exc_info.value)


def test_format_contexts_empty() -> None:
    """Test formatting empty contexts."""
    trace = MagicMock(spec=TraceLogger)
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test"}):
        tool = LLMTool(trace)
        result = tool._format_contexts([])
        assert result == ""


def test_format_contexts_with_content() -> None:
    """Test formatting contexts with content."""
    trace = MagicMock(spec=TraceLogger)
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test"}):
        tool = LLMTool(trace)
        contexts = [
            {
                "path": "src/main.py",
                "functions": [{"name": "hello", "lines": "1-5"}],
                "classes": [{"name": "Greeter", "lines": "10-20"}],
                "content": "def hello():\n    print('world')",
            }
        ]
        result = tool._format_contexts(contexts)
        assert "File: src/main.py" in result
        assert "Functions: hello" in result
        assert "Classes: Greeter" in result
        assert "def hello():" in result


def test_format_contexts_truncates_long_content() -> None:
    """Test that long content is truncated."""
    trace = MagicMock(spec=TraceLogger)
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test"}):
        tool = LLMTool(trace)
        long_content = "x" * 3000
        contexts = [
            {
                "path": "src/main.py",
                "functions": [],
                "classes": [],
                "content": long_content,
            }
        ]
        result = tool._format_contexts(contexts)
        assert "... [truncated]" in result
        assert len(result) < 2500  # Should be truncated


def test_strip_code_fence_removes_markdown() -> None:
    """Test stripping code fences from model output."""
    text = "```diff\n- old\n+ new\n```"
    result = LLMTool._strip_code_fence(text)
    assert result == "- old\n+ new"


def test_strip_code_fence_preserves_non_fenced() -> None:
    """Test that non-fenced text is preserved."""
    text = "- old\n+ new"
    result = LLMTool._strip_code_fence(text)
    assert result == text


def test_strip_code_fence_handles_empty() -> None:
    """Test stripping empty text."""
    result = LLMTool._strip_code_fence("")
    assert result == ""


def test_strip_code_fence_handles_language_tag() -> None:
    """Test stripping with different language tags."""
    text = "```python\nprint('hello')\n```"
    result = LLMTool._strip_code_fence(text)
    assert result == "print('hello')"


def test_fence_re_matches_wrapped_content() -> None:
    """Test the fence regex pattern."""
    match = _FENCE_RE.match("```diff\ncontent\n```")
    assert match is not None
    assert match.group(1) == "content"

    match = _FENCE_RE.match("```python\nline1\nline2\n```")
    assert match is not None
    assert match.group(1) == "line1\nline2"


def test_generate_patch_success(llm_tool: LLMTool) -> None:
    """Test successful patch generation."""
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content="- old\n+ new\nRATIONALE: Fixed the bug"))
    ]

    with patch.object(
        llm_tool.client.chat.completions, "create", return_value=mock_completion
    ):
        diff, rationale = llm_tool.generate_patch(
            "Fix the bug",
            [{"path": "src/main.py", "functions": [], "classes": [], "content": "old"}],
        )

    assert diff == "- old\n+ new"
    assert rationale == "Fixed the bug"


def test_generate_patch_no_rationale(llm_tool: LLMTool) -> None:
    """Test patch generation when no RATIONALE: marker is present."""
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="- old\n+ new"))]

    with patch.object(
        llm_tool.client.chat.completions, "create", return_value=mock_completion
    ):
        diff, rationale = llm_tool.generate_patch(
            "Fix the bug",
            [{"path": "src/main.py", "functions": [], "classes": [], "content": "old"}],
        )

    assert diff == "- old\n+ new"
    assert rationale == "- old\n+ new"  # Falls back to full response


def test_explain_patch_success(llm_tool: LLMTool) -> None:
    """Test successful patch explanation."""
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content="This patch fixes the bug by..."))
    ]

    with patch.object(
        llm_tool.client.chat.completions, "create", return_value=mock_completion
    ):
        rationale = llm_tool.explain_patch("- old\n+ new")

    assert "fixes the bug" in rationale


def test_llm_error_on_api_failure(llm_tool: LLMTool) -> None:
    """Test that API failures raise LLMError."""
    with patch.object(
        llm_tool.client.chat.completions,
        "create",
        side_effect=Exception("API error"),
    ):
        with pytest.raises(LLMError) as exc_info:
            llm_tool.generate_patch(
                "Fix the bug",
                [
                    {
                        "path": "src/main.py",
                        "functions": [],
                        "classes": [],
                        "content": "old",
                    }
                ],
            )
        assert "API error" in str(exc_info.value)


def test_trace_logging_in_llm_calls(llm_tool: LLMTool) -> None:
    """Test that LLM calls are traced."""
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="response"))]

    with patch.object(
        llm_tool.client.chat.completions, "create", return_value=mock_completion
    ):
        llm_tool.explain_patch("- old\n+ new")

    # Verify trace was called
    llm_tool.trace_logger.log.assert_called_once()
    call_args = llm_tool.trace_logger.log.call_args
    assert call_args.kwargs["tool_name"] == "llm_explain_patch"
