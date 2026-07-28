"""Tests for the agent orchestrator."""

from __future__ import annotations

from unittest.mock import patch

from coding_agent.models import RunRequest, RunResult
from coding_agent.orchestrator import AgentOrchestrator


def test_parse_repo_owner_repo_format() -> None:
    """Test parsing owner/repo format."""
    orch = AgentOrchestrator()
    owner, repo = orch._parse_repo("myorg/myrepo")
    assert owner == "myorg"
    assert repo == "myrepo"


def test_parse_repo_url_format() -> None:
    """Test parsing full GitHub URL."""
    orch = AgentOrchestrator()
    owner, repo = orch._parse_repo("https://github.com/myorg/myrepo")
    assert owner == "myorg"
    assert repo == "myrepo"


def test_parse_repo_url_with_git_suffix() -> None:
    """Test parsing URL with .git suffix."""
    orch = AgentOrchestrator()
    owner, repo = orch._parse_repo("https://github.com/myorg/myrepo.git")
    assert owner == "myorg"
    assert repo == "myrepo"


def test_extract_keywords() -> None:
    """Test keyword extraction from issue text."""
    orch = AgentOrchestrator()
    text = "The export button crashes when clicking on large datasets"
    keywords = orch._extract_keywords(text)
    assert "export" in keywords
    assert "crashes" in keywords
    assert "datasets" in keywords
    assert "the" not in keywords.lower().split()


def test_insufficient_context_empty_issue() -> None:
    """Test that empty issue text returns insufficient_context."""
    orch = AgentOrchestrator()
    request = RunRequest(repo="owner/repo", issue_text="")

    with patch.object(orch.github, "validate_repo", return_value={}):
        result = orch.run(request)

    assert isinstance(result, RunResult)
    assert result.status == "insufficient_context"
    assert result.reason is not None
