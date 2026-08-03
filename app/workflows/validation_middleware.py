"""Automatically validate Wiki Markdown after filesystem mutations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path, PurePosixPath
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.api.schema import ValidationReport
from app.tools.index_builder import build_draft_indexes
from app.tools.wiki_validator import validate_page


_WRITE_TOOLS = {"write_file", "edit_file"}
_DRAFT_PREFIX = "/generated-wiki/drafts/"
_RESERVED_FILES = {"index.md"}

ToolResult = ToolMessage | Command[Any]
SyncToolHandler = Callable[[ToolCallRequest], ToolResult]
AsyncToolHandler = Callable[[ToolCallRequest], Awaitable[ToolResult]]


class WikiValidationMiddleware(AgentMiddleware):
    """Keep generated Wiki pages valid and synchronize their index."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root.resolve()

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: SyncToolHandler,
    ) -> ToolResult:
        """Run a filesystem tool, then validate the Markdown it changed."""

        page_path = _wiki_page_path(request)
        result = handler(request)
        if page_path is None or not _tool_succeeded(result):
            return result
        return _append_validation_feedback(
            result,
            validate_page(
                self._project_root,
                page_path,
                allow_pending_indexes=True,
                lightweight=True,
            ),
        )

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: AsyncToolHandler,
    ) -> ToolResult:
        """Async equivalent used when the Agent is invoked asynchronously."""

        page_path = _wiki_page_path(request)
        result = await handler(request)
        if page_path is None or not _tool_succeeded(result):
            return result
        return _append_validation_feedback(
            result,
            validate_page(
                self._project_root,
                page_path,
                allow_pending_indexes=True,
                lightweight=True,
            ),
        )

    def after_agent(self, state: Any, runtime: Any) -> None:
        """Synchronize the deterministic Wiki index after a successful run."""

        del state, runtime
        build_draft_indexes(self._project_root)

    async def aafter_agent(self, state: Any, runtime: Any) -> None:
        """Async lifecycle equivalent for asynchronously invoked Agents."""

        del state, runtime
        build_draft_indexes(self._project_root)


def _wiki_page_path(request: ToolCallRequest) -> str | None:
    tool_call = request.tool_call
    if tool_call.get("name") not in _WRITE_TOOLS:
        return None
    args = tool_call.get("args")
    if not isinstance(args, dict):
        return None
    raw_path = args.get("file_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None

    normalized = "/" + raw_path.strip().replace("\\", "/").lstrip("/")
    path = PurePosixPath(normalized)
    if (
        not normalized.startswith(_DRAFT_PREFIX)
        or path.suffix.lower() != ".md"
        or path.name.lower() in _RESERVED_FILES
        or ".." in path.parts
    ):
        return None
    return normalized


def _tool_succeeded(result: ToolResult) -> bool:
    messages = _tool_messages(result)
    return any(message.status != "error" for message in messages)


def _append_validation_feedback(
    result: ToolResult,
    report: ValidationReport,
) -> ToolResult:
    if not report.issues:
        return result

    feedback = _format_feedback(report)
    for message in _tool_messages(result):
        if message.status == "error":
            continue
        if isinstance(message.content, str):
            message.content = f"{message.content}\n\n{feedback}"
        elif isinstance(message.content, list):
            message.content = [
                *message.content,
                {"type": "text", "text": feedback},
            ]
        else:
            message.content = feedback
    return result


def _tool_messages(result: ToolResult) -> list[ToolMessage]:
    if isinstance(result, ToolMessage):
        return [result]
    if not isinstance(result, Command) or not isinstance(result.update, dict):
        return []
    messages = result.update.get("messages")
    if not isinstance(messages, list):
        return []
    return [message for message in messages if isinstance(message, ToolMessage)]


def _format_feedback(report: ValidationReport) -> str:
    details = "\n".join(
        f"- [{issue.level}/{issue.code}] {issue.path}: {issue.message}"
        for issue in report.issues
    )
    return (
        "WARNING: 刚写入的 Wiki 页面未通过自动校验。\n"
        f"{details}\n"
        "你必须根据以上问题修正该页面；无法确定的事实写入 uncertainties，"
        "不得编造内容或来源。"
    )
