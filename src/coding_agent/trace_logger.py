"""Trace logger for recording every tool call."""

from __future__ import annotations

import datetime
import json
import os
import re
from typing import Any

from coding_agent.models import ToolCallRecord

# Known secret-shaped patterns to redact before anything is persisted.
# Deliberately pattern-based (not a fixed list of known key prefixes)
# so it catches the *shape* of a credential even if a new token format
# is introduced later. Order matters only in that more-specific patterns
# should be listed first if they ever overlap.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),  # GitHub PAT (classic)
    re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),  # GitHub PAT (fine-grained)
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),  # Groq API key
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]{20,}=*", re.IGNORECASE),
    re.compile(r"Authorization[\"']?\s*:\s*[\"']?[^\s,}\"']{10,}", re.IGNORECASE),
]

_REDACTED = "[REDACTED]"


def _redact(value: Any) -> Any:
    """Recursively redact secret-shaped strings from a JSON-serializable value.

    Walks dicts and lists to catch secrets nested inside tool inputs or
    outputs (e.g. an Authorization header buried in a params dict), not
    just top-level fields. Redacts entire matched substrings, not just
    the key name, so a token embedded mid-string is still caught.

    Args:
        value: Any JSON-serializable value (dict, list, str, or scalar).

    Returns:
        The same structure with secret-shaped substrings replaced.
    """
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(_REDACTED, redacted)
        return redacted
    return value


class TraceLogger:
    """Records tool calls and writes trace files at the end of a run."""

    def __init__(self, run_id: str, output_dir: str = "./output") -> None:
        """Initialize the trace logger."""
        self.run_id = run_id
        self.output_dir = output_dir
        self.records: list[ToolCallRecord] = []

    def log(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: dict[str, Any] | None,
        error: str | None,
        duration_ms: int,
    ) -> None:
        """Record a single tool call.

        Input, output, and the error message are redacted for
        secret-shaped substrings (Rules.md §6, §10; Architecture.md §8)
        before being held in memory, not just at write-time -- so a
        crash between log() and write() can't leave an unredacted copy
        anywhere trace data is read from.
        """
        record = ToolCallRecord(
            tool_name=tool_name,
            input=_redact(tool_input),
            output=_redact(tool_output),
            error=_redact(error),
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
            duration_ms=duration_ms,
        )
        self.records.append(record)

    def write(self) -> str:
        """Write the accumulated trace to a JSON file."""
        os.makedirs(self.output_dir, exist_ok=True)
        trace_path = os.path.join(self.output_dir, f"{self.run_id}.trace.json")
        data = {
            "run_id": self.run_id,
            "record_count": len(self.records),
            "records": [
                {
                    "tool_name": r.tool_name,
                    "input": r.input,
                    "output": r.output,
                    "error": r.error,
                    "timestamp": r.timestamp.isoformat(),
                    "duration_ms": r.duration_ms,
                }
                for r in self.records
            ],
        }
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return trace_path
