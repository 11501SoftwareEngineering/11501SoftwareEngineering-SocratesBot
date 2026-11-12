"""Dialogue history, reply, and end. Creating a session stays on the topic routes."""

import json
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, get_db
from app.schemas.dialogue import (
    DialogueHistoryResponse,
    EndDialogueRequest,
    EndDialogueResponse,
    StreamDone,
    StreamMessageRequest,
)
from app.services import dialogue as dialogue_service
from app.services.model_client import OpenAIChatClient

router = APIRouter(tags=["dialogue"])


def _sse(done: StreamDone) -> Iterator[str]:
    lines = done.text.splitlines() or [""]
    for line in lines:
        yield f"data: {line}\n"
    yield "\n"
    payload = json.dumps(
        {
            "message_id": str(done.message_id),
            "completed_turns": done.completed_turns,
            "is_completed": done.is_completed,
            "awaiting_end_consent": done.awaiting_end_consent,
        }
    )
    yield f"event: done\ndata: {payload}\n\n"


@router.get(
    "/sessions/{sessionId}/messages",
    response_model=DialogueHistoryResponse,
)
async def read_dialogue_messages(
    sessionId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DialogueHistoryResponse:
    return await dialogue_service.read_history(
        db,
        user_id=current_user.id,
        session_id=sessionId,
    )


@router.post("/sessions/{sessionId}/messages/stream")
async def stream_dialogue_reply(
    sessionId: UUID,
    payload: StreamMessageRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    done = await dialogue_service.send_reply(
        db,
        OpenAIChatClient(),
        user_id=current_user.id,
        session_id=sessionId,
        content=payload.content,
        request_id=payload.request_id,
    )
    return StreamingResponse(_sse(done), media_type="text/event-stream")


@router.post(
    "/sessions/{sessionId}/end",
    response_model=EndDialogueResponse,
)
async def end_dialogue(
    sessionId: UUID,
    payload: EndDialogueRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EndDialogueResponse:
    return await dialogue_service.end_dialogue(
        db,
        user_id=current_user.id,
        session_id=sessionId,
        action=payload.action,
    )
