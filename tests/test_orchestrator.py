# tests/test_orchestrator.py
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


def test_extract_keywords_removes_stop_words() -> None:
    """Test that stop words are removed from keywords."""
    orch = AgentOrchestrator()
    text = "This is a test of the emergency broadcast system"
    keywords = orch._extract_keywords(text)
    # Stop words should be removed
    assert "test" in keywords
    assert "emergency" in keywords
    assert "broadcast" in keywords
    assert "system" in keywords
    assert "this" not in keywords.lower().split()
    assert "is" not in keywords.lower().split()


def test_insufficient_context_empty_issue() -> None:
    """Test that empty issue text returns insufficient_context."""
    orch = AgentOrchestrator()
    request = RunRequest(repo="owner/repo", issue_text="")

    with patch.object(orch.github, "validate_repo", return_value={}):
        result = orch.run(request)

    assert isinstance(result, RunResult)
    assert result.status == "insufficient_context"
    assert result.reason is not None


def test_insufficient_context_whitespace_issue() -> None:
    """Test that whitespace-only issue text returns insufficient_context."""
    orch = AgentOrchestrator()
    request = RunRequest(repo="owner/repo", issue_text="   \n   ")

    with patch.object(orch.github, "validate_repo", return_value={}):
        result = orch.run(request)

    assert result.status == "insufficient_context"
    assert "Empty or missing" in (result.reason or "")


def test_system_failure_on_untyped_error() -> None:
    """Test that untyped errors become status="error" not insufficient_context."""
    orch = AgentOrchestrator()
    request = RunRequest(repo="owner/repo", issue_text="test")

    # Force an untyped error in validate_repo
    with patch.object(orch.github, "validate_repo", side_effect=ValueError("untyped")):
        result = orch.run(request)

    assert result.status == "error"
    assert "untyped" in (result.reason or "")


def test_resolve_issue_text_uses_url_precedence() -> None:
    """Test that issue_url takes precedence over raw text."""
    orch = AgentOrchestrator()
    request = RunRequest(
        repo="owner/repo",
        issue_text="raw text",
        issue_url="https://github.com/owner/repo/issues/42",
    )

    with patch.object(orch.github, "get_issue", return_value="issue body"):
        result = orch._resolve_issue_text(request, "owner", "repo")

    assert "issue body" in result
    assert "raw text" in result  # Raw text is appended as supplementary


def test_resolve_issue_text_without_url() -> None:
    """Test that raw text is used when no URL is provided."""
    orch = AgentOrchestrator()
    request = RunRequest(repo="owner/repo", issue_text="raw description")

    result = orch._resolve_issue_text(request, "owner", "repo")
    assert result == "raw description"


def test_resolve_issue_text_handles_malformed_url() -> None:
    """Test that malformed URL doesn't break resolution."""
    orch = AgentOrchestrator()
    request = RunRequest(
        repo="owner/repo",
        issue_text="raw text",
        issue_url="https://github.com/owner/repo/not-an-issue/42",
    )

    # Should fall back to raw text
    result = orch._resolve_issue_text(request, "owner", "repo")
    assert result == "raw text"
