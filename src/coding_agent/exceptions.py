"""Typed exception hierarchy for the coding agent."""


class CodingAgentError(Exception):
    """Base exception for all coding agent errors."""


class GitHubError(CodingAgentError):
    """Base for GitHub API errors."""


class GitHubRateLimitError(GitHubError):
    """Raised when GitHub API returns a rate limit response."""


class GitHubNotFoundError(GitHubError):
    """Raised when a GitHub resource is not found."""


class GitHubAuthError(GitHubError):
    """Raised when GitHub authentication fails."""


class ASTError(CodingAgentError):
    """Base for AST parsing errors."""


class ASTParseError(ASTError):
    """Raised when both ast and tree-sitter fail to parse a file."""


class LLMError(CodingAgentError):
    """Base for LLM API errors."""


class ValidationError(CodingAgentError):
    """Base for patch validation errors."""


class BudgetExhaustedError(CodingAgentError):
    """Raised when the tool-call budget is exhausted."""
