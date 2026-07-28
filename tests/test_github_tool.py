"""Tests for the GitHub tool."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from coding_agent.exceptions import (
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from coding_agent.github_tool import GitHubTool
from coding_agent.trace_logger import TraceLogger


@pytest.fixture
def github_tool() -> GitHubTool:
    """Create a GitHubTool with a mock trace logger."""
    trace = MagicMock(spec=TraceLogger)
    return GitHubTool(trace)


def test_validate_repo_success(github_tool: GitHubTool) -> None:
    """Test validate_repo on successful response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 123, "name": "test-repo"}

    with patch.object(github_tool.session, "request", return_value=mock_response):
        result = github_tool.validate_repo("owner", "repo")

    assert result["name"] == "test-repo"


def test_validate_repo_not_found(github_tool: GitHubTool) -> None:
    """Test validate_repo raises GitHubNotFoundError on 404."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with (
        patch.object(github_tool.session, "request", return_value=mock_response),
        pytest.raises(GitHubNotFoundError),
    ):
        github_tool.validate_repo("owner", "nonexistent")


def test_validate_repo_rate_limit(github_tool: GitHubTool) -> None:
    """Test validate_repo raises GitHubRateLimitError on 429."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited"

    with (
        patch.object(github_tool.session, "request", return_value=mock_response),
        pytest.raises(GitHubRateLimitError),
    ):
        github_tool.validate_repo("owner", "repo")


def test_validate_repo_auth_error(github_tool: GitHubTool) -> None:
    """Test validate_repo raises GitHubAuthError on 401."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with (
        patch.object(github_tool.session, "request", return_value=mock_response),
        pytest.raises(GitHubAuthError),
    ):
        github_tool.validate_repo("owner", "repo")
