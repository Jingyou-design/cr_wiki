"""HTTP handling for Wiki chat endpoints."""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import HTTPException, status
from starlette.responses import StreamingResponse

from app.api.schema import AuthenticatedUserContext, ChatRequest, WorkflowContext
from app.config.settings import settings
from app.workflows.chat import stream_chat


async def handle_chat(
    request: ChatRequest,
    user: AuthenticatedUserContext,
) -> StreamingResponse:
    context = WorkflowContext(project_root=settings.wiki_project_root.resolve())
    try:
        conversation_id, events = await stream_chat(
            context,
            question=request.question,
            conversation_id=request.conversation_id,
            user=user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return StreamingResponse(
        _encode_events(conversation_id, events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
async def _encode_events(
    conversation_id: str,
    events: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    yield _encode_sse(
        "start",
        {
            "type": "start",
            "conversation_id": conversation_id,
        },
    )
    async for event in events:
        yield _encode_sse(str(event["type"]), event)


def _encode_sse(event_type: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_type}\ndata: {payload}\n\n"
