"""GitHub API tool wrapper."""

from __future__ import annotations

import base64
import os
import time
from typing import Any, cast

import requests

from coding_agent.exceptions import (
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from coding_agent.trace_logger import TraceLogger


class GitHubTool:
    """Read-only GitHub REST API wrapper with typed errors and trace logging."""

    BASE_URL = "https://api.github.com"
    # GitHub rate-limits code search to 10 requests/minute for authenticated
    # users; self-throttle search calls to respect it and avoid 429s during
    # evaluation. Class attribute so tests can set it to 0.
    SEARCH_MIN_INTERVAL_SECONDS = 6.2

    def __init__(self, trace_logger: TraceLogger) -> None:
        """Initialize with a trace logger.

        Args:
            trace_logger: Logger for recording tool calls.
        """
        self.trace_logger = trace_logger
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        self._last_search_at = 0.0

    def _throttle_search(self) -> None:
        """Sleep if needed to respect the code-search rate limit."""
        elapsed = time.perf_counter() - self._last_search_at
        wait = self.SEARCH_MIN_INTERVAL_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_search_at = time.perf_counter()

    def _call(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated GitHub API call with tracing.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path (without base URL).
            params: Optional query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            GitHubRateLimitError: On 429 or rate-limit headers.
            GitHubNotFoundError: On 404.
            GitHubAuthError: On 401 or 403 auth failures.
            GitHubError: On other non-2xx responses.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        start = time.perf_counter()
        error_msg: str | None = None
        response_data: dict[str, Any] = {}

        try:
            response = self.session.request(method, url, params=params)
            if response.status_code == 429:
                raise GitHubRateLimitError(f"GitHub rate limit hit: {response.text}")
            if response.status_code == 404:
                raise GitHubNotFoundError(f"GitHub resource not found: {url}")
            if response.status_code in (401, 403):
                raise GitHubAuthError(
                    f"GitHub auth failed ({response.status_code}): " f"{response.text}"
                )
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
            response_data = data
            return data
        except requests.HTTPError as exc:
            error_msg = f"GitHub API error: {exc}"
            raise GitHubError(error_msg) from exc
        except (
            GitHubRateLimitError,
            GitHubNotFoundError,
            GitHubAuthError,
        ) as exc:
            error_msg = str(exc)
            raise
        except requests.RequestException as exc:
            error_msg = f"GitHub request failed: {exc}"
            raise GitHubError(error_msg) from exc
        except Exception as exc:
            # Never let an untyped transport/connection error escape the tool:
            # Rules.md §5 requires every failure to surface as a typed
            # CodingAgentError so the orchestrator can route it to the
            # designed insufficient-context path. Re-raise as GitHubError.
            error_msg = f"GitHub request failed: {exc}"
            raise GitHubError(error_msg) from exc
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.trace_logger.log(
                tool_name="github",
                tool_input={
                    "method": method,
                    "endpoint": endpoint,
                    "params": params,
                },
                tool_output=response_data,
                error=error_msg,
                duration_ms=duration_ms,
            )

    def validate_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """Validate that a repo exists and is accessible.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Repo metadata from GitHub.
        """
        return self._call("GET", f"/repos/{owner}/{repo}")

    def search_code(
        self,
        query: str,
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Search code within GitHub.

        Code search has a tight rate limit (10 req/min), so self-throttle to
        avoid 429s and a mid-run rate-limit failure during evaluation.
        """
        self._throttle_search()
        data = self._call(
            "GET",
            "/search/code",
            params={"q": query, "per_page": per_page},
        )
        return cast(list[dict[str, Any]], data.get("items", []))

    def get_file(self, owner: str, repo: str, path: str) -> str:
        """Fetch the raw content of a file.

        Args:
            owner: Repository owner.
            repo: Repository name.
            path: File path within the repo.

        Returns:
            File content as a string.
        """
        data = self._call("GET", f"/repos/{owner}/{repo}/contents/{path}")
        content = data.get("content", "")
        if content:
            return base64.b64decode(content).decode("utf-8")
        return ""

    def get_issue(self, owner: str, repo: str, number: int) -> str:
        """Fetch issue body text.

        Args:
            owner: Repository owner.
            repo: Repository name.
            number: Issue number.

        Returns:
            Issue body text.
        """
        data = self._call("GET", f"/repos/{owner}/{repo}/issues/{number}")
        return data.get("body", "") or ""
