"""Tests for the CLI entry point."""

from __future__ import annotations

import sys
from unittest.mock import patch

from coding_agent.cli import main


def test_cli_fix_not_implemented(capsys) -> None:
    """Verify the fix command exits cleanly with the placeholder."""
    with patch.object(
        sys, "argv", ["coding-agent", "fix", "--repo", "x/y", "--issue", "test"]
    ):
        code = main()

    assert code == 0
    captured = capsys.readouterr()
    assert "Not yet implemented" in captured.out


def test_cli_missing_issue(capsys) -> None:
    """Verify the CLI rejects missing issue text and URL."""
    with patch.object(sys, "argv", ["coding-agent", "fix", "--repo", "x/y"]):
        code = main()

    assert code == 1
    captured = capsys.readouterr()
    assert "either --issue or --issue-url" in captured.err


def test_cli_no_command_prints_help(capsys) -> None:
    """Verify running without a subcommand prints help."""
    with patch.object(sys, "argv", ["coding-agent"]):
        code = main()

    assert code == 1
    captured = capsys.readouterr()
    assert "usage:" in captured.out
