from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GenerationStatus
from app.models.course import CourseMembership
from app.models.message import DialogueMessage
from app.models.report_attempt import ReportAttempt
from app.models.session import Session
from app.models.user import User


async def list_for_session(db: AsyncSession, session_id: UUID) -> list[ReportAttempt]:
    statement = (
        select(ReportAttempt)
        .where(ReportAttempt.session_id == session_id)
        .order_by(ReportAttempt.created_at, ReportAttempt.id)
    )
    return list(await db.scalars(statement))


async def list_for_sessions(
    db: AsyncSession, session_ids: list[UUID]
) -> list[ReportAttempt]:
    if not session_ids:
        return []
    statement = (
        select(ReportAttempt)
        .where(ReportAttempt.session_id.in_(session_ids))
        .order_by(ReportAttempt.created_at, ReportAttempt.id)
    )
    return list(await db.scalars(statement))


async def insert_pending(db: AsyncSession, session_id: UUID) -> ReportAttempt:
    attempt = ReportAttempt(
        session_id=session_id, status=GenerationStatus.PENDING.value
    )
    db.add(attempt)
    await db.flush()
    return attempt


async def get_attempt(db: AsyncSession, attempt_id: UUID) -> ReportAttempt | None:
    return await db.get(ReportAttempt, attempt_id)


async def mark_processing(db: AsyncSession, attempt_id: UUID) -> None:
    await db.execute(
        update(ReportAttempt)
        .where(
            ReportAttempt.id == attempt_id,
            ReportAttempt.status == GenerationStatus.PENDING.value,
        )
        .values(
            status=GenerationStatus.PROCESSING.value,
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        )
    )


async def mark_ready(db: AsyncSession, attempt_id: UUID, body: dict) -> None:
    await db.execute(
        update(ReportAttempt)
        .where(
            ReportAttempt.id == attempt_id,
            ReportAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(status=GenerationStatus.READY.value, result_json=body)
    )


async def mark_failed(db: AsyncSession, attempt_id: UUID) -> None:
    await db.execute(
        update(ReportAttempt)
        .where(
            ReportAttempt.id == attempt_id,
            ReportAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(status=GenerationStatus.FAILED.value)
    )


async def owned_session(
    db: AsyncSession, *, session_id: UUID, user_id: UUID
) -> Session | None:
    session = await db.get(Session, session_id)
    if session is None or session.user_id != user_id:
        return None
    return session


async def topic_dialogues(
    db: AsyncSession, topic_id: UUID
) -> list[tuple[Session, str]]:
    statement = (
        select(Session, User.name)
        .join(User, User.id == Session.user_id)
        .where(Session.topic_id == topic_id)
    )
    rows = await db.execute(statement)
    return [(session, name) for session, name in rows.all()]


async def class_size(db: AsyncSession, course_id: UUID) -> int:
    statement = (
        select(func.count())
        .select_from(CourseMembership)
        .where(
            CourseMembership.course_id == course_id,
            CourseMembership.role == "STUDENT",
            CourseMembership.left_at.is_(None),
        )
    )
    return int(await db.scalar(statement) or 0)


async def student_turn_count(db: AsyncSession, session_id: UUID) -> int:
    statement = select(DialogueMessage).where(
        DialogueMessage.session_id == session_id,
        DialogueMessage.sender == "student",
    )
    return len(list(await db.scalars(statement)))
