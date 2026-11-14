"""One dialogue: history, a waiting reply stream, and end actions."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogueOutcome, SessionStatus
from app.crud import message as message_crud
from app.models.message import DialogueMessage
from app.models.session import Session
from app.models.topic import Topic
from app.schemas.dialogue import (
    DialogueHistoryResponse,
    DialogueMessageItem,
    EndDialogueResponse,
    StreamDone,
)
from app.services.model_client import ModelCallError, ModelClient

# ponytail: one process. A second worker will not see this lock; a DB lease is the upgrade.
_BUSY: set[UUID] = set()

REPLY_INSTRUCTIONS = (
    "You are guiding one Socratic inquiry. Reply in the inquiry's content language. "
    "Do not name the student. Use exclusions 'unspecified' when none were given. "
    "Set goal_reached only when the inquiry goal is met."
)


class ReplyRejected(Exception):
    """A reply or end action this dialogue will not accept."""

    def __init__(
        self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def guard_reply(
    *,
    stage: str,
    outcome: str,
    completed_turns: int,
    max_turns: int | None,
) -> None:
    """Reject a reply when the dialogue is closed or the turn cap is spent.

    Raises:
        ReplyRejected: the dialogue is not accepting replies, or the turn cap is reached.
    """
    if stage != "conversation" or outcome != DialogueOutcome.OPEN.value:
        raise ReplyRejected("Dialogue is not accepting replies")
    if max_turns is not None and completed_turns >= max_turns:
        raise ReplyRejected("Turn cap reached")


def apply_end(
    action: str,
    *,
    outcome: str,
    status_value: str,
    goal_reached: bool,
) -> tuple[str, str, bool, bool, str]:
    """Return outcome, status, goal_reached, awaiting_end_consent, message."""
    if outcome != DialogueOutcome.OPEN.value:
        raise ReplyRejected("Dialogue has already ended")
    if action == "complete":
        if not goal_reached:
            raise ReplyRejected(
                "Inquiry goal is not met",
                status.HTTP_409_CONFLICT,
            )
        return (
            DialogueOutcome.COMPLETED.value,
            SessionStatus.COMPLETED.value,
            True,
            False,
            "Dialogue completed",
        )
    if action == "continue":
        return (
            DialogueOutcome.OPEN.value,
            status_value,
            False,
            False,
            "Dialogue continues",
        )
    return (
        DialogueOutcome.ABANDONED.value,
        SessionStatus.IN_PROGRESS.value,
        False,
        False,
        "Dialogue abandoned",
    )


def reply_material(topic: Topic, messages: list[DialogueMessage]) -> str:
    """Build the model prompt from the saved inquiry and the messages so far."""
    lines = [
        f"topic: {topic.inquiry_topic or ''}",
        f"core_question: {topic.core_question or ''}",
        f"inquiry_focus: {topic.inquiry_focus or ''}",
        f"background_info: {topic.background_info or ''}",
        f"exclusions: {topic.exclusions or 'unspecified'}",
        f"content_language: {topic.content_language or ''}",
        f"age_band: {topic.age_band or ''}",
    ]
    for message in messages:
        lines.append(f"{message.sender}: {message.content}")
    return "\n".join(lines)


def _history(
    session: Session,
    topic: Topic,
    messages: list[DialogueMessage],
) -> DialogueHistoryResponse:
    return DialogueHistoryResponse(
        messages=[
            DialogueMessageItem(
                message_id=message.id,
                sender=message.sender,
                content=message.content,
                created_at=message.created_at,
            )
            for message in messages
        ],
        session_status=session.outcome,
        max_turns=topic.max_turns,
        completed_turns=sum(message.sender == "student" for message in messages),
        goal_reached=session.goal_reached,
        awaiting_end_consent=session.awaiting_end_consent,
    )


def _saved_reply(
    messages: list[DialogueMessage],
    request_id: UUID,
) -> DialogueMessage | None:
    seen = False
    for message in messages:
        if message.request_id == request_id:
            seen = True
            continue
        if seen and message.sender == "ai":
            return message
    return None


async def read_history(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
) -> DialogueHistoryResponse:
    """Return one student's own dialogue.

    Raises:
        HTTPException: 404 if the session is missing or belongs to someone else.
    """
    loaded = await message_crud.load_owned_dialogue(
        db,
        session_id=session_id,
        user_id=user_id,
    )
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    session, topic, messages = loaded
    return _history(session, topic, messages)


async def send_reply(
    db: AsyncSession,
    client: ModelClient,
    *,
    user_id: UUID,
    session_id: UUID,
    content: str,
    request_id: UUID,
) -> StreamDone:
    """Store one student turn and return the model reply.

    Raises:
        HTTPException: 404 if the session is missing; 400 if replies are closed
            or the turn cap is spent; 409 if another reply is in progress;
            502 or 503 if the model call fails.
    """
    loaded = await message_crud.load_owned_dialogue(
        db,
        session_id=session_id,
        user_id=user_id,
    )
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    session, topic, messages = loaded
    saved = _saved_reply(messages, request_id)
    if saved is not None:
        return StreamDone(
            message_id=saved.id,
            text=saved.content,
            completed_turns=sum(message.sender == "student" for message in messages),
            is_completed=session.outcome == DialogueOutcome.COMPLETED.value,
            awaiting_end_consent=session.awaiting_end_consent,
        )
    try:
        guard_reply(
            stage=topic.stage,
            outcome=session.outcome,
            completed_turns=sum(message.sender == "student" for message in messages),
            max_turns=topic.max_turns,
        )
    except ReplyRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if session_id in _BUSY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another reply is in progress",
        )
    _BUSY.add(session_id)
    try:
        text, goal_reached = await client.complete_reply(
            instructions=REPLY_INSTRUCTIONS,
            material=reply_material(topic, messages),
        )
        message_id = await message_crud.save_exchange(
            db,
            session_id=session_id,
            content=content,
            request_id=request_id,
            reply=text,
            goal_reached=goal_reached,
        )
        await db.commit()
    except ModelCallError as exc:
        await db.rollback()
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.status_code in {429, 503}
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail="Model call failed") from exc
    except Exception:
        await db.rollback()
        raise
    finally:
        _BUSY.discard(session_id)
    completed_turns = sum(message.sender == "student" for message in messages) + 1
    return StreamDone(
        message_id=message_id,
        text=text,
        completed_turns=completed_turns,
        is_completed=False,
        awaiting_end_consent=goal_reached,
    )


async def end_dialogue(
    db: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    action: str,
) -> EndDialogueResponse:
    """Complete, continue, or abandon this student's dialogue.

    Raises:
        HTTPException: 404 if the session is missing; 400 if it has already
            ended; 409 if complete is requested before the goal is met.
    """
    loaded = await message_crud.load_owned_dialogue(
        db,
        session_id=session_id,
        user_id=user_id,
    )
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    session, _topic, _messages = loaded
    try:
        outcome, status_value, goal_reached, awaiting, message = apply_end(
            action,
            outcome=session.outcome,
            status_value=session.status,
            goal_reached=session.goal_reached,
        )
    except ReplyRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    await message_crud.save_end(
        db,
        session_id=session_id,
        outcome=outcome,
        status=status_value,
        goal_reached=goal_reached,
        awaiting_end_consent=awaiting,
    )
    await db.commit()
    return EndDialogueResponse(
        session_id=session_id,
        session_status=outcome,
        message=message,
    )
