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


class SystemFailureError(CodingAgentError):
    """Raised for unexpected failures that are not a graceful stopping
    condition — distinct from BudgetExhaustedError, GitHubNotFoundError,
    or a validation failure, all of which mean "we correctly determined
    we can't proceed." This means something broke that shouldn't have.

    The orchestrator maps this to RunResult.status == "error" rather
    than "insufficient_context", so failure-rate metrics (Evaluator,
    PRD §4) can distinguish infrastructure breakage from the agent
    correctly declining to guess.
    """
