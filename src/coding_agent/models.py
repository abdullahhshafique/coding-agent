"""Data models for the coding agent."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FunctionNode:
    """Represents a function definition in the AST."""

    name: str
    start_line: int
    end_line: int


@dataclass
class ClassNode:
    """Represents a class definition in the AST."""

    name: str
    start_line: int
    end_line: int


@dataclass
class RunRequest:
    """Input parameters for a single agent run."""

    repo: str
    issue_text: str | None = None
    issue_url: str | None = None
    tool_call_budget: int = 20


@dataclass
class ToolCallRecord:
    """Log entry for a single tool invocation."""

    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    timestamp: datetime.datetime
    duration_ms: int


@dataclass
class FileStructure:
    """Structural representation of a parsed source file."""

    path: str
    language: str
    functions: list[FunctionNode] = field(default_factory=list)
    classes: list[ClassNode] = field(default_factory=list)
    parse_method: str = "ast"
    truncated: bool = False


@dataclass
class GenerationResult:
    """Output of the patch generation step."""

    diff_text: str
    rationale: str
    files_touched: list[str]
    valid: bool
    validation_error: str | None


@dataclass
class RunResult:
    """Final result of a complete agent run."""

    status: str
    patch_path: str | None
    trace_path: str
    rationale: str | None
    reason: str | None


@dataclass
class RunState:
    """Mutable state container for a single agent run."""

    request: RunRequest
    trace: list[ToolCallRecord] = field(default_factory=list)
    candidates: list[FileStructure] = field(default_factory=list)
    remaining_budget: int = 0
