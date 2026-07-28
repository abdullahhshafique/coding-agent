"""Trace logger for recording every tool call."""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from coding_agent.models import ToolCallRecord


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
        """Record a single tool call."""
        record = ToolCallRecord(
            tool_name=tool_name,
            input=tool_input,
            output=tool_output,
            error=error,
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
