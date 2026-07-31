# tests/test_github_tool.py
"""Tests for the GitHub tool."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
from coding_agent.exceptions import (
    GitHubAuthError,
    GitHubError,
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


def test_search_code_success(github_tool: GitHubTool) -> None:
    """Test search_code returns results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {"path": "src/main.py", "name": "main.py"},
            {"path": "src/utils.py", "name": "utils.py"},
        ]
    }

    with patch.object(github_tool.session, "request", return_value=mock_response):
        results = github_tool.search_code("repo:owner/repo test", per_page=5)

    assert len(results) == 2
    assert results[0]["path"] == "src/main.py"


def test_search_code_empty_results(github_tool: GitHubTool) -> None:
    """Test search_code handles empty results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"items": []}

    with patch.object(github_tool.session, "request", return_value=mock_response):
        results = github_tool.search_code("repo:owner/repo nonexistent")

    assert results == []


def test_get_file_success(github_tool: GitHubTool) -> None:
    """Test get_file decodes base64 content correctly."""
    content = "def hello():\n    return 'world'\n"
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"content": encoded}

    with patch.object(github_tool.session, "request", return_value=mock_response):
        result = github_tool.get_file("owner", "repo", "src/main.py")

    assert result == content


def test_get_file_not_found(github_tool: GitHubTool) -> None:
    """Test get_file raises GitHubNotFoundError on 404."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with (
        patch.object(github_tool.session, "request", return_value=mock_response),
        pytest.raises(GitHubNotFoundError),
    ):
        github_tool.get_file("owner", "repo", "nonexistent.py")


def test_get_issue_success(github_tool: GitHubTool) -> None:
    """Test get_issue returns issue body."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"body": "This is the issue description"}

    with patch.object(github_tool.session, "request", return_value=mock_response):
        result = github_tool.get_issue("owner", "repo", 1)

    assert result == "This is the issue description"


def test_get_issue_empty_body(github_tool: GitHubTool) -> None:
    """Test get_issue handles empty body."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"body": ""}

    with patch.object(github_tool.session, "request", return_value=mock_response):
        result = github_tool.get_issue("owner", "repo", 1)

    assert result == ""


def test_github_error_on_connection_failure(github_tool: GitHubTool) -> None:
    """Test that connection failures raise GitHubError."""
    with (
        patch.object(
            github_tool.session,
            "request",
            side_effect=Exception("Connection refused"),
        ),
        pytest.raises(GitHubError),
    ):
        github_tool.validate_repo("owner", "repo")


def test_trace_logging_in_github_calls(github_tool: GitHubTool) -> None:
    """Test that GitHub calls are traced."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 123}

    with patch.object(github_tool.session, "request", return_value=mock_response):
        github_tool.validate_repo("owner", "repo")

    # Verify trace was called
    github_tool.trace_logger.log.assert_called_once()
    call_args = github_tool.trace_logger.log.call_args
    assert call_args.kwargs["tool_name"] == "github"
    assert call_args.kwargs["tool_input"]["endpoint"] == "/repos/owner/repo"
