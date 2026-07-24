"""Answer grounded employee questions with a read-only Deep Agent."""

from __future__ import annotations

import re
from threading import Lock
from typing import Any
from uuid import uuid4

from app.api.schema import ChatResponse, ChatTurn, WorkflowContext
from app.prompt.loader import create_chat_user_prompt
from app.workflows.agent_factory import create_chat_agent


_CONVERSATION_LOCK = Lock()
_CONVERSATIONS: dict[str, list[ChatTurn]] = {}
_MAX_RETAINED_TURNS = 12
_SOURCE_PATTERN = re.compile(
    r"`/?((?:generated-wiki/drafts|company-handbook)/[^`\r\n]+)`",
    flags=re.IGNORECASE,
)


class ChatSourceNotReadyError(RuntimeError):
    """Raised when chat is requested before company sources are installed."""


class ChatWikiNotInitializedError(RuntimeError):
    """Raised when Wiki-first chat is requested before a valid Wiki entry exists."""


class ChatExecutionError(RuntimeError):
    """Raised when the chat Agent cannot complete a grounded answer."""


def run_chat(
    context: WorkflowContext,
    *,
    question: str,
    conversation_id: str | None,
) -> ChatResponse:
    """Run one grounded question and retain bounded conversational context."""

    if not (context.project_root / "company-handbook").is_dir():
        raise ChatSourceNotReadyError(
            "公司资料尚未处理完成，暂时不能进行知识库问答。"
        )
    quickstart = (
        context.project_root.resolve()
        / "generated-wiki"
        / "drafts"
        / "quickstart.md"
    )
    root_index = quickstart.with_name("index.md")
    if not quickstart.is_file() or not root_index.is_file():
        raise ChatWikiNotInitializedError(
            "Wiki 尚未初始化完成，请上传资料包并生成知识库。"
        )
    resolved_id = conversation_id or uuid4().hex
    with _CONVERSATION_LOCK:
        history = list(_CONVERSATIONS.get(resolved_id, []))
    messages = [
        {"role": turn.role, "content": turn.content}
        for turn in history
    ]
    messages.append(
        {
            "role": "user",
            "content": create_chat_user_prompt(question),
        }
    )

    try:
        result = create_chat_agent(context).invoke({"messages": messages})
    except ValueError:
        raise
    except Exception as exc:
        raise ChatExecutionError("知识库问答 Agent 执行失败。") from exc

    answer = _final_message_text(result).strip()
    if not answer:
        raise ChatExecutionError("知识库问答 Agent 没有返回有效回答。")
    sources = list(dict.fromkeys(_SOURCE_PATTERN.findall(answer)))

    retained = [
        *history,
        ChatTurn(role="user", content=question.strip()),
        ChatTurn(role="assistant", content=answer),
    ][-_MAX_RETAINED_TURNS:]
    with _CONVERSATION_LOCK:
        _CONVERSATIONS[resolved_id] = retained

    return ChatResponse(
        conversation_id=resolved_id,
        answer=answer,
        sources=sources,
    )


def clear_chat(conversation_id: str) -> bool:
    """Forget one in-memory conversation and return whether it existed."""

    with _CONVERSATION_LOCK:
        return _CONVERSATIONS.pop(conversation_id, None) is not None


def _final_message_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        return str(result)
    content = getattr(messages[-1], "content", "")
    return content if isinstance(content, str) else str(content)
