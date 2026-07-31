# tests/test_cli.py
"""Tests for the CLI entry point."""

from __future__ import annotations

import sys
from unittest.mock import patch

from coding_agent.cli import main


def test_cli_fix_runs_without_crash() -> None:
    """Verify the fix command invokes orchestrator without crashing."""
    with patch.object(
        sys, "argv", ["coding-agent", "fix", "--repo", "x/y", "--issue", "test"]
    ):
        with patch("coding_agent.cli.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.run.return_value.status = "success"
            code = main()

    assert code == 0


def test_cli_missing_issue() -> None:
    """Verify the CLI rejects missing issue text and URL."""
    with patch.object(sys, "argv", ["coding-agent", "fix", "--repo", "x/y"]):
        with patch("sys.stderr.write") as mock_stderr:
            code = main()
            assert code == 1
            mock_stderr.assert_called()


def test_cli_no_command_prints_help() -> None:
    """Verify running without a subcommand prints help."""
    with patch.object(sys, "argv", ["coding-agent"]):
        with patch("argparse.ArgumentParser.print_help") as mock_help:
            code = main()
            assert code == 1
            mock_help.assert_called_once()


def test_cli_with_issue_url() -> None:
    """Verify the fix command works with --issue-url."""
    with patch.object(
        sys, "argv", ["coding-agent", "fix", "--repo", "x/y", "--issue-url", "https://github.com/x/y/issues/1"]
    ):
        with patch("coding_agent.cli.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.run.return_value.status = "success"
            code = main()

    assert code == 0


def test_cli_requires_repo() -> None:
    """Verify the CLI rejects missing repo."""
    with patch.object(sys, "argv", ["coding-agent", "fix", "--issue", "test"]):
        with patch("argparse.ArgumentParser.print_help") as mock_help:
            code = main()
            assert code == 1
            mock_help.assert_called_once()


def test_cli_budget_parameter() -> None:
    """Verify the --budget parameter is passed correctly."""
    with patch.object(
        sys,
        "argv",
        ["coding-agent", "fix", "--repo", "x/y", "--issue", "test",
         "--budget", "30"],
    ):
        with patch("coding_agent.cli.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.run.return_value.status = "success"
            code = main()

            # Check that the budget parameter was passed correctly
            call_args = mock_orch.return_value.run.call_args
            assert call_args is not None
            request = call_args[0][0]
            assert request.tool_call_budget == 30
            assert code == 0
