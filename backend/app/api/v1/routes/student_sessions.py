"""Dialogue history, reply, and end. Creating a session stays on the topic routes."""

import json
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, get_db
from app.api.openapi_responses import (
    DIALOGUE_END_RESPONSES,
    DIALOGUE_READ_RESPONSES,
    DIALOGUE_STREAM_RESPONSES,
)
from app.schemas.dialogue import (
    DialogueHistoryResponse,
    EndDialogueRequest,
    EndDialogueResponse,
    StreamDone,
    StreamDoneEvent,
    StreamMessageRequest,
)
from app.services import dialogue as dialogue_service
from app.services.model_client import OpenAIChatClient

router = APIRouter(tags=["dialogue"])


def _sse(done: StreamDone) -> Iterator[str]:
    # SSE uses CR/LF framing, not Python's broader Unicode splitlines rules.
    # Keep trailing empty lines so the decoded text retains its final newline.
    lines = done.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line in lines:
        yield f"data: {line}\n"
    yield "\n"
    payload = json.dumps(
        StreamDoneEvent.model_validate(done.model_dump()).model_dump(mode="json")
    )
    yield f"event: done\ndata: {payload}\n\n"


@router.get(
    "/sessions/{sessionId}/messages",
    response_model=DialogueHistoryResponse,
    responses=DIALOGUE_READ_RESPONSES,
)
async def read_dialogue_messages(
    sessionId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DialogueHistoryResponse:
    """Return this student's messages for the dialogue."""
    return await dialogue_service.read_history(
        db,
        user_id=current_user.id,
        session_id=sessionId,
    )


@router.post(
    "/sessions/{sessionId}/messages/stream",
    response_class=StreamingResponse,
    responses=DIALOGUE_STREAM_RESPONSES,
)
async def stream_dialogue_reply(
    sessionId: UUID,
    payload: StreamMessageRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Return one unnamed text event, then a named `done` JSON event.

    Inference and persistence finish before the SSE response starts; this is not
    token-by-token provider streaming. Failures before that point are JSON HTTP
    errors. Retry the same logical submission with the same request_id/content:
    a committed reply is replayed without another model call. A request_id is not
    a guarantee of exactly-once provider billing after an ambiguous failure.
    """
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
    responses=DIALOGUE_END_RESPONSES,
)
async def end_dialogue(
    sessionId: UUID,
    payload: EndDialogueRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EndDialogueResponse:
    """Complete only after goal achievement, continue, or abandon.

    Continue clears consent but retains goal achievement. Complete does not start
    report generation: call POST /sessions/{sessionId}/report separately.
    Abandoned and closed_by_summary dialogues are not report-eligible.
    """
    return await dialogue_service.end_dialogue(
        db,
        user_id=current_user.id,
        session_id=sessionId,
        action=payload.action,
    )
