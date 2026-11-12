from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogueOutcome, SessionStatus
from app.models.message import DialogueMessage
from app.models.session import Session
from app.models.topic import Topic


async def load_owned_dialogue(
    db: AsyncSession,
    *,
    session_id: UUID,
    user_id: UUID,
) -> tuple[Session, Topic, list[DialogueMessage]] | None:
    """Return the dialogue only for its owner. Anyone else looks the same as missing."""
    session = await db.get(Session, session_id)
    if session is None or session.user_id != user_id:
        return None
    topic = await db.get(Topic, session.topic_id)
    if topic is None:
        return None
    messages = list(
        await db.scalars(
            select(DialogueMessage)
            .where(DialogueMessage.session_id == session_id)
            .order_by(DialogueMessage.created_at, DialogueMessage.id)
        )
    )
    return session, topic, messages


async def count_student_turns(db: AsyncSession, session_id: UUID) -> int:
    statement = (
        select(func.count())
        .select_from(DialogueMessage)
        .where(
            DialogueMessage.session_id == session_id,
            DialogueMessage.sender == "student",
        )
    )
    return int(await db.scalar(statement) or 0)


async def save_exchange(
    db: AsyncSession,
    *,
    session_id: UUID,
    content: str,
    request_id: UUID,
    reply: str,
    goal_reached: bool,
) -> UUID:
    now = datetime.now(UTC)
    db.add(
        DialogueMessage(
            session_id=session_id,
            sender="student",
            content=content,
            request_id=request_id,
            created_at=now,
        )
    )
    ai_message = DialogueMessage(
        session_id=session_id,
        sender="ai",
        content=reply,
        created_at=now,
    )
    db.add(ai_message)
    await db.flush()
    if goal_reached:
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(goal_reached=True, awaiting_end_consent=True)
        )
    return ai_message.id


async def save_end(
    db: AsyncSession,
    *,
    session_id: UUID,
    outcome: str,
    status: str,
    goal_reached: bool,
    awaiting_end_consent: bool,
) -> None:
    values: dict[str, object] = {
        "outcome": outcome,
        "status": status,
        "goal_reached": goal_reached,
        "awaiting_end_consent": awaiting_end_consent,
    }
    if status == SessionStatus.COMPLETED.value:
        values["completed_at"] = datetime.now(UTC)
    if outcome == DialogueOutcome.ABANDONED.value:
        values["status"] = SessionStatus.IN_PROGRESS.value
        values.pop("completed_at", None)
    await db.execute(update(Session).where(Session.id == session_id).values(**values))
