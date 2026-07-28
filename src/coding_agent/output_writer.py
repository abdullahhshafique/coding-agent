"""Write patch, rationale, and trace to disk."""

from __future__ import annotations

import os
from datetime import datetime

from coding_agent.models import RunResult
from coding_agent.trace_logger import TraceLogger


class OutputWriter:
    """Persists run artifacts to the output directory."""

    def __init__(self, output_dir: str = "./output") -> None:
        """Initialize with output directory."""
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def write(
        self,
        repo: str,
        diff_text: str,
        rationale: str,
        trace_logger: TraceLogger,
    ) -> RunResult:
        """Write all run artifacts."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_repo = repo.replace("/", "-")
        base_name = f"{safe_repo}-{timestamp}"

        patch_path = os.path.join(self.output_dir, f"{base_name}.patch")
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(diff_text)

        trace_path = trace_logger.write()

        sep = "=" * 60
        print()
        print(sep)
        print("PATCH GENERATED")
        print(sep)
        print(f"Patch saved to: {patch_path}")
        print(f"Trace saved to: {trace_path}")
        print()
        print("Rationale:")
        print(rationale)
        print(sep)

        return RunResult(
            status="success",
            patch_path=patch_path,
            trace_path=trace_path,
            rationale=rationale,
            reason=None,
        )
