"""Tests for the CLI entry point."""

from __future__ import annotations

import sys
from unittest.mock import patch

from coding_agent.cli import main


def test_cli_fix_runs_without_crash(capsys) -> None:
    """Verify the fix command invokes orchestrator without crashing."""
    with patch.object(
        sys, "argv", ["coding-agent", "fix", "--repo", "x/y", "--issue", "test"]
    ):
        with patch("coding_agent.cli.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.run.return_value.status = "success"
            code = main()

    assert code == 0


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
