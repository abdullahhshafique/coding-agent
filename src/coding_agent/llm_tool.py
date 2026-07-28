"""LLM tool wrapping Groq API for patch generation."""

from __future__ import annotations

import os
import time
from typing import Any

from groq import Groq

from coding_agent.exceptions import LLMError
from coding_agent.trace_logger import TraceLogger


class LLMTool:
    """Wrapper around Groq API for generating patches and explanations."""

    MODEL = "llama-3.3-70b-versatile"
    MAX_TOKENS = 4096
    TEMPERATURE = 0.2

    def __init__(self, trace_logger: TraceLogger) -> None:
        """Initialize with a trace logger.

        Args:
            trace_logger: Logger for recording tool calls.
        """
        self.trace_logger = trace_logger
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise LLMError("GROQ_API_KEY environment variable not set")
        self.client = Groq(api_key=api_key)

    def generate_patch(
        self,
        issue_text: str,
        file_contexts: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Generate a unified diff patch for the given issue.

        Args:
            issue_text: Description of the bug or feature.
            file_contexts: List of structured file contexts from AST parsing.

        Returns:
            Tuple of (diff_text, rationale).
        """
        system_prompt = (
            "You are a coding assistant. You receive a bug description and "
            "structured file contexts. Your job is to produce a unified diff "
            "patch that fixes the bug. Output ONLY the diff in standard "
            "unified diff format, followed by a brief rationale. "
            "Do NOT output markdown code blocks around the diff. "
            "The diff must be applyable with git apply."
        )

        context_str = self._format_contexts(file_contexts)
        user_prompt = (
            "Bug description:"
            + "\n"
            + issue_text
            + "\n\n"
            + "Relevant files:"
            + "\n"
            + context_str
            + "\n\n"
            + "Generate a unified diff patch. After the diff, "
            + "add a line RATIONALE: followed by your explanation."
        )

        return self._call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_name="llm_generate_patch",
        )

    def explain_patch(self, diff_text: str) -> str:
        """Generate a plain-language explanation of a patch.

        Args:
            diff_text: The unified diff to explain.

        Returns:
            Plain-language rationale string.
        """
        system_prompt = (
            "You are a coding assistant. Explain the following patch "
            "in plain language suitable for a code review."
        )
        user_prompt = "Patch:" + "\n" + diff_text + "\n\n" + "Explain this patch."

        _, rationale = self._call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_name="llm_explain_patch",
        )
        return rationale

    def _call(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
    ) -> tuple[str, str]:
        """Make a Groq API call with tracing.

        Args:
            system_prompt: System-level instructions.
            user_prompt: User-level prompt content.
            tool_name: Name for trace logging.

        Returns:
            Tuple of (raw_response, parsed_rationale_or_full).
        """
        start = time.perf_counter()
        error_msg: str | None = None
        response_text = ""

        try:
            completion = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.TEMPERATURE,
                max_completion_tokens=self.MAX_TOKENS,
            )  # type: ignore[call-overload]
            response_text = completion.choices[0].message.content or ""

            if "RATIONALE:" in response_text:
                parts = response_text.split("RATIONALE:", 1)
                diff_part = parts[0].strip()
                rationale_part = parts[1].strip()
                return diff_part, rationale_part

            return response_text, response_text
        except Exception as exc:
            error_msg = f"Groq API call failed: {exc}"
            raise LLMError(error_msg) from exc
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.trace_logger.log(
                tool_name=tool_name,
                tool_input={
                    "model": self.MODEL,
                    "system_prompt_length": len(system_prompt),
                    "user_prompt_length": len(user_prompt),
                },
                tool_output={
                    "response_length": len(response_text),
                    "response_preview": response_text[:200],
                },
                error=error_msg,
                duration_ms=duration_ms,
            )

    def _format_contexts(
        self,
        file_contexts: list[dict[str, Any]],
    ) -> str:
        """Format file contexts for the prompt.

        Args:
            file_contexts: Structured file data.

        Returns:
            Formatted string for the LLM prompt.
        """
        parts: list[str] = []
        for ctx in file_contexts:
            path = ctx.get("path", "unknown")
            functions = ctx.get("functions", [])
            classes = ctx.get("classes", [])
            content = ctx.get("content", "")

            part = f"File: {path}" + "\n"
            if functions:
                func_names = ", ".join(f["name"] for f in functions)
                part += f"  Functions: {func_names}" + "\n"
            if classes:
                class_names = ", ".join(c["name"] for c in classes)
                part += f"  Classes: {class_names}" + "\n"
            if content:
                truncated = content[:2000]
                if len(content) > 2000:
                    truncated += "... [truncated]"
                part += "  Content:" + "\n" + truncated + "\n"
            parts.append(part)

        return ("\n" + "---" + "\n").join(parts)
