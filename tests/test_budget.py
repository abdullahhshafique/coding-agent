"""Tests for budget enforcement."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from coding_agent.exceptions import BudgetExhaustedError
from coding_agent.models import RunRequest, RunResult, RunState
from coding_agent.orchestrator import AgentOrchestrator


def test_budget_enforcement_stops_run() -> None:
    """Test that budget=0 stops the run immediately."""
    orch = AgentOrchestrator()
    request = RunRequest(repo="owner/repo", issue_text="test", tool_call_budget=0)

    with patch.object(orch.github, "validate_repo", return_value={}):
        result = orch.run(request)

    assert isinstance(result, RunResult)
    assert result.status == "insufficient_context"
    assert "budget" in (result.reason or "").lower()


def test_budget_decrements_on_each_call() -> None:
    """Test that budget decrements with each tool call."""
    orch = AgentOrchestrator()
    state = RunState(
        request=RunRequest(repo="x/y", tool_call_budget=5),
        remaining_budget=5,
    )

    orch._check_budget(state)
    assert state.remaining_budget == 4

    orch._check_budget(state)
    assert state.remaining_budget == 3


def test_budget_exhausted_raises() -> None:
    """Test that budget below 0 raises BudgetExhaustedError."""
    orch = AgentOrchestrator()
    state = RunState(
        request=RunRequest(repo="x/y", tool_call_budget=1),
        remaining_budget=0,
    )

    with pytest.raises(BudgetExhaustedError):
        orch._check_budget(state)
