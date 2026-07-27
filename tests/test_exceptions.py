"""Tests for the exception hierarchy."""

from __future__ import annotations

from coding_agent.exceptions import (
    ASTParseError,
    BudgetExhaustedError,
    CodingAgentError,
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


def test_base_exception_is_base() -> None:
    """Verify CodingAgentError is the root."""
    assert issubclass(CodingAgentError, Exception)


def test_github_errors_inherit_from_github_error() -> None:
    """Verify GitHub errors share a common parent."""
    assert issubclass(GitHubRateLimitError, GitHubError)
    assert issubclass(GitHubNotFoundError, GitHubError)
    assert issubclass(GitHubAuthError, GitHubError)


def test_all_exceptions_inherit_from_base() -> None:
    """Verify all custom exceptions inherit from CodingAgentError."""
    assert issubclass(GitHubRateLimitError, CodingAgentError)
    assert issubclass(GitHubNotFoundError, CodingAgentError)
    assert issubclass(GitHubAuthError, CodingAgentError)
    assert issubclass(ASTParseError, CodingAgentError)
    assert issubclass(BudgetExhaustedError, CodingAgentError)


def test_exception_can_be_raised_and_caught() -> None:
    """Verify the exception mechanism works."""
    try:
        raise GitHubRateLimitError("rate limited")
    except CodingAgentError as exc:
        assert "rate limited" in str(exc)
