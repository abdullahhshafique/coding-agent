# tests/test_trace_logger.py
"""Tests for the trace logger and redaction."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coding_agent.trace_logger import _REDACTED, TraceLogger, _redact


def test_redact_github_pat() -> None:
    """Test redaction of GitHub personal access tokens."""
    token = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
    assert _redact(token) == _REDACTED

    mixed = f"Authorization: Bearer {token}"
    result = _redact(mixed)
    assert _REDACTED in result
    assert token not in result


def test_redact_github_fine_grained_pat() -> None:
    """Test redaction of GitHub fine-grained PATs."""
    token = (
        "github_pat_11ABCDEFGHIJKLMNOPQRSTUVWXYZ_"
        "1234567890abcdefghijklmnopqrstuvwxyz"
    )
    assert _redact(token) == _REDACTED


def test_redact_groq_key() -> None:
    """Test redaction of Groq API keys."""
    key = "gsk_abcdefghijklmnopqrstuvwxyz1234567890"
    assert _redact(key) == _REDACTED


def test_redact_authorization_header() -> None:
    """Test redaction of Authorization headers."""
    header = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"
    result = _redact(header)
    assert _REDACTED in result


def test_redact_nested_dict() -> None:
    """Test redaction of secret-shaped strings nested in dicts."""
    data = {
        "headers": {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz"},
        "body": {"token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"},
    }
    result = _redact(data)
    assert result["headers"]["Authorization"] == _REDACTED
    assert result["body"]["token"] == _REDACTED


def test_redact_list() -> None:
    """Test redaction of secret-shaped strings in lists."""
    data = ["normal text", "ghp_abcdefghijklmnopqrstuvwxyz1234567890", "more text"]
    result = _redact(data)
    assert result[0] == "normal text"
    assert result[1] == _REDACTED
    assert result[2] == "more text"


def test_redact_preserves_non_secrets() -> None:
    """Test that non-secret text is preserved."""
    text = "This is a normal string with no secrets"
    assert _redact(text) == text

    data = {"key": "value", "nested": {"foo": "bar"}}
    result = _redact(data)
    assert result == data


def test_trace_logger_redacts_inputs() -> None:
    """Test that trace logger redacts secret-shaped inputs."""
    logger = TraceLogger("test-run-id")
    logger.log(
        tool_name="github",
        tool_input={"token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"},
        tool_output=None,
        error=None,
        duration_ms=100,
    )

    assert logger.records[0].input["token"] == _REDACTED


def test_trace_logger_redacts_outputs() -> None:
    """Test that trace logger redacts secret-shaped outputs."""
    logger = TraceLogger("test-run-id")
    logger.log(
        tool_name="github",
        tool_input={},
        tool_output={"api_key": "gsk_abcdefghijklmnopqrstuvwxyz1234567890"},
        error=None,
        duration_ms=100,
    )

    assert logger.records[0].output["api_key"] == _REDACTED


def test_trace_logger_redacts_errors() -> None:
    """Test that trace logger redacts secret-shaped error messages."""
    logger = TraceLogger("test-run-id")
    logger.log(
        tool_name="github",
        tool_input={},
        tool_output=None,
        error="Failed with token ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        duration_ms=100,
    )

    assert _REDACTED in logger.records[0].error
    assert "ghp_" not in logger.records[0].error


def test_trace_logger_write_creates_file() -> None:
    """Test that write creates a JSON trace file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = TraceLogger("test-run-id", output_dir=tmpdir)
        logger.log(
            tool_name="test",
            tool_input={"key": "value"},
            tool_output={"result": "ok"},
            error=None,
            duration_ms=50,
        )

        path = logger.write()
        assert Path(path).exists()

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["run_id"] == "test-run-id"
        assert data["record_count"] == 1
        assert data["records"][0]["tool_name"] == "test"
        assert data["records"][0]["input"] == {"key": "value"}


def test_trace_logger_multiple_records() -> None:
    """Test that multiple records are stored correctly."""
    logger = TraceLogger("test-run-id")

    logger.log("tool1", {"a": 1}, None, None, 10)
    logger.log("tool2", {"b": 2}, {"c": 3}, None, 20)

    assert len(logger.records) == 2
    assert logger.records[0].tool_name == "tool1"
    assert logger.records[1].tool_name == "tool2"
