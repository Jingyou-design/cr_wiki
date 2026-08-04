"""Answer grounded employee questions with a read-only Deep Agent."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver

from app.api.schema import AuthenticatedUserContext, WorkflowContext
from app.prompt.loader import create_chat_user_prompt
from app.workflows.agent_factory import create_chat_agent
from app.workflows.auth import department_for
from app.workflows.permissions import get_chat_permissions


_CHAT_CHECKPOINTER = InMemorySaver()
_CHAT_AGENT_CACHE: dict[tuple[str, str, str], Any] = {}
_SOURCE_PATTERN = re.compile(
    r"`/?((?:generated-wiki/drafts|company-handbook)/[^`\r\n]+)`",
    flags=re.IGNORECASE,
)


async def stream_chat(
    context: WorkflowContext,
    *,
    question: str,
    conversation_id: str | None,
    user: AuthenticatedUserContext,
) -> tuple[str, AsyncIterator[dict[str, Any]]]:
    """Stream one checkpointed answer as text deltas and a final source event."""

    resolved_id = conversation_id or uuid4().hex
    config = {"configurable": {"thread_id": resolved_id}}
    agent = _get_chat_agent(context, user)
    messages = [
        {
            "role": "user",
            "content": create_chat_user_prompt(question),
        }
    ]

    async def events() -> AsyncIterator[dict[str, Any]]:
        answer_parts: list[str] = []
        try:
            stream = await agent.astream_events(
                {"messages": messages},
                config=config,
                version="v3",
            )
            async with stream:
                async for message in stream.messages:
                    async for delta in message.text:
                        if delta:
                            answer_parts.append(delta)
                            yield {"type": "delta", "content": delta}
        except Exception:
            yield {
                "type": "error",
                "detail": "知识库问答 Agent 执行失败。",
            }
            return

        answer = "".join(answer_parts).strip()
        if not answer:
            yield {
                "type": "error",
                "detail": "知识库问答 Agent 没有返回有效回答。",
            }
            return
        sources = list(dict.fromkeys(_SOURCE_PATTERN.findall(answer)))
        yield {"type": "done", "sources": sources}

    return resolved_id, events()


def _get_chat_agent(
    context: WorkflowContext,
    user: AuthenticatedUserContext,
) -> Any:
    department = department_for(user)
    scope = (
        "admin"
        if user.role == "admin"
        else f"{user.role}:{department.code}"
    )
    key = (
        str(context.project_root.resolve()),
        user.config_revision,
        scope,
    )
    cached = _CHAT_AGENT_CACHE.get(key)
    if cached is not None:
        return cached
    permissions = get_chat_permissions(user, department)
    agent = create_chat_agent(
        context,
        checkpointer=_CHAT_CHECKPOINTER,
        permissions=permissions,
        user=user,
        department=department,
    )
    stale = [
        item
        for item in _CHAT_AGENT_CACHE
        if item[1] != user.config_revision
    ]
    for item in stale:
        _CHAT_AGENT_CACHE.pop(item, None)
    _CHAT_AGENT_CACHE[key] = agent
    return agent
