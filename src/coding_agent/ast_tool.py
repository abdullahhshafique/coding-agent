"""AST parsing tool with tree-sitter fallback."""

from __future__ import annotations

import ast
import time
from typing import Any

from coding_agent.exceptions import ASTParseError
from coding_agent.models import ClassNode, FileStructure, FunctionNode
from coding_agent.trace_logger import TraceLogger

# Maximum lines to include in raw content sent to the LLM. Kept high because
# hard-truncating a large source file (e.g. click/core.py ~3000 lines) would
# silently drop the very function the patch must edit, guaranteeing a wrong or
# inapplicable diff. Oversized-file *safety* is still enforced by truncation
# here plus the per-content cap in LLM context formatting; the PRD §6.3 intent
# (don't blow up on pathological inputs) is preserved at this higher bound.
MAX_CONTENT_LINES = 4000


class ASTTool:
    """Parse Python source into structured FileStructure objects."""

    def __init__(self, trace_logger: TraceLogger) -> None:
        """Initialize with a trace logger.

        Args:
            trace_logger: Logger for recording tool calls.
        """
        self.trace_logger = trace_logger

    def parse_python(self, source: str, path: str) -> FileStructure:
        """Parse Python source code into structural representation.

        Tries stdlib `ast` first, falls back to tree-sitter on failure.
        Truncates content if file exceeds MAX_CONTENT_LINES.

        Args:
            source: Raw source code text.
            path: File path (for metadata).

        Returns:
            FileStructure with extracted functions and classes.
        """
        start = time.perf_counter()
        error_msg: str | None = None
        result: FileStructure | None = None
        truncated = False
        content = source

        # Truncate oversized files
        lines = source.splitlines()
        if len(lines) > MAX_CONTENT_LINES:
            truncated = True
            content = "\n".join(lines[:MAX_CONTENT_LINES])
            content += (
                "\n\n# ... [truncated: "
                f"{len(lines) - MAX_CONTENT_LINES} lines omitted]"
            )

        try:
            tree = ast.parse(source)
            functions: list[FunctionNode] = []
            classes: list[ClassNode] = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(
                        FunctionNode(
                            name=node.name,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                        )
                    )
                elif isinstance(node, ast.ClassDef):
                    classes.append(
                        ClassNode(
                            name=node.name,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                        )
                    )

            result = FileStructure(
                path=path,
                language="python",
                functions=functions,
                classes=classes,
                parse_method="ast",
                truncated=truncated,
                raw_content=content,
            )
            return result
        except SyntaxError:
            try:
                result = self._parse_with_tree_sitter(source, path, truncated, content)
                return result
            except Exception as exc:
                error_msg = f"Both ast and tree-sitter failed: {exc}"
                raise ASTParseError(error_msg) from exc
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.trace_logger.log(
                tool_name="ast",
                tool_input={"path": path, "source_length": len(source)},
                tool_output=(
                    {
                        "language": result.language if result else None,
                        "function_count": len(result.functions) if result else 0,
                        "class_count": len(result.classes) if result else 0,
                        "parse_method": result.parse_method if result else None,
                        "truncated": result.truncated if result else False,
                    }
                    if result
                    else None
                ),
                error=error_msg,
                duration_ms=duration_ms,
            )

    def _parse_with_tree_sitter(
        self,
        source: str,
        path: str,
        truncated: bool,
        content: str,
    ) -> FileStructure:
        """Parse using tree-sitter as fallback.

        Args:
            source: Raw source code text.
            path: File path (for metadata).
            truncated: Whether content was truncated.
            content: Potentially truncated content for raw_content field.

        Returns:
            FileStructure with extracted functions and classes.
        """
        try:
            import tree_sitter_python as tspython
            from tree_sitter import Language, Parser
        except ImportError:
            raise ASTParseError("tree-sitter-python not installed")

        parser = Parser(Language(tspython.language()))
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node

        functions: list[FunctionNode] = []
        classes: list[ClassNode] = []

        def _walk(node: Any) -> None:
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "<anon>"
                functions.append(
                    FunctionNode(
                        name=name,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                    )
                )
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "<anon>"
                classes.append(
                    ClassNode(
                        name=name,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                    )
                )
            for child in node.children:
                _walk(child)

        _walk(root)

        return FileStructure(
            path=path,
            language="python",
            functions=functions,
            classes=classes,
            parse_method="tree-sitter",
            truncated=truncated,
            raw_content=content,
        )
