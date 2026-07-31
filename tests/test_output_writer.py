# tests/test_output_writer.py
"""Tests for the output writer."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from coding_agent.output_writer import OutputWriter
from coding_agent.trace_logger import TraceLogger


def test_write_creates_patch_file() -> None:
    """Test that write creates a patch file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = OutputWriter(output_dir=tmpdir)
        trace_logger = MagicMock(spec=TraceLogger)
        trace_logger.write.return_value = "/tmp/trace.json"

        result = writer.write(
            repo="owner/repo",
            diff_text="--- a/file.py\n+++ b/file.py\n- old\n+ new",
            rationale="Fixed the bug",
            trace_logger=trace_logger,
        )

        assert result.status == "success"
        assert result.patch_path is not None
        assert Path(result.patch_path).exists()
        assert result.rationale == "Fixed the bug"

        # Verify the patch content
        with open(result.patch_path, encoding="utf-8") as f:
            content = f.read()
        assert "--- a/file.py" in content


def test_write_creates_directory() -> None:
    """Test that write creates the output directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "nested" / "output"
        writer = OutputWriter(output_dir=str(output_dir))
        trace_logger = MagicMock(spec=TraceLogger)
        trace_logger.write.return_value = "/tmp/trace.json"

        result = writer.write(
            repo="owner/repo",
            diff_text="- old\n+ new",
            rationale="Fixed",
            trace_logger=trace_logger,
        )

        assert output_dir.exists()
        assert result.patch_path is not None


def test_write_sanitizes_repo_name() -> None:
    """Test that repo name is sanitized for filenames."""
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = OutputWriter(output_dir=tmpdir)

        result = writer.write(
            repo="owner/with/slashes/repo",
            diff_text="- old\n+ new",
            rationale="Fixed",
            trace_logger=MagicMock(spec=TraceLogger),
        )

        # The repo name should have slashes replaced with dashes
        assert "owner-with-slashes-repo" in result.patch_path
