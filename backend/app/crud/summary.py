from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogueOutcome, GenerationStatus
from app.models.class_summary import ClassSummary, PublishedSummary, SummaryAttempt
from app.models.report_attempt import ReportAttempt
from app.models.session import Session
from app.models.topic import Topic


async def ready_report_bodies(
    db: AsyncSession, topic_id: UUID
) -> list[tuple[str, dict]]:
    statement = (
        select(ReportAttempt)
        .join(Session, Session.id == ReportAttempt.session_id)
        .where(
            Session.topic_id == topic_id,
            ReportAttempt.status == GenerationStatus.READY.value,
            ReportAttempt.result_json.is_not(None),
        )
        .order_by(ReportAttempt.created_at, ReportAttempt.id)
    )
    rows = list(await db.scalars(statement))
    latest: dict[UUID, ReportAttempt] = {}
    for row in rows:
        latest[row.session_id] = row
    return [(str(row.id), row.result_json or {}) for row in latest.values()]


async def insert_attempt(
    db: AsyncSession, *, topic_id: UUID, request_json: dict
) -> SummaryAttempt:
    attempt = SummaryAttempt(
        topic_id=topic_id,
        status=GenerationStatus.PENDING.value,
        request_json=request_json,
    )
    db.add(attempt)
    await db.flush()
    return attempt


async def get_attempt(db: AsyncSession, attempt_id: UUID) -> SummaryAttempt | None:
    return await db.get(SummaryAttempt, attempt_id)


async def latest_attempt(db: AsyncSession, topic_id: UUID) -> SummaryAttempt | None:
    statement = (
        select(SummaryAttempt)
        .where(SummaryAttempt.topic_id == topic_id)
        .order_by(SummaryAttempt.created_at.desc(), SummaryAttempt.id.desc())
        .limit(1)
    )
    return await db.scalar(statement)


async def mark_processing(db: AsyncSession, attempt_id: UUID) -> None:
    await db.execute(
        update(SummaryAttempt)
        .where(
            SummaryAttempt.id == attempt_id,
            SummaryAttempt.status == GenerationStatus.PENDING.value,
        )
        .values(
            status=GenerationStatus.PROCESSING.value,
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        )
    )


async def mark_failed(db: AsyncSession, attempt_id: UUID) -> None:
    await db.execute(
        update(SummaryAttempt)
        .where(
            SummaryAttempt.id == attempt_id,
            SummaryAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(status=GenerationStatus.FAILED.value)
    )


async def next_version(db: AsyncSession, topic_id: UUID) -> int:
    statement = select(func.max(ClassSummary.version)).where(
        ClassSummary.topic_id == topic_id
    )
    current = await db.scalar(statement)
    return int(current or 0) + 1


def _draft_row(topic_id: UUID, version: int, draft: dict) -> ClassSummary:
    return ClassSummary(
        topic_id=topic_id,
        version=version,
        status="draft",
        overview=draft["overview"],
        viewpoint_summary=draft["viewpoint_summary"],
        denominator=draft["denominator"],
        groups=draft["groups"],
        ungrouped_report_ids=draft["ungrouped_report_ids"],
    )


async def _close_open_dialogues(db: AsyncSession, topic: Topic) -> None:
    if topic.stage != "conversation":
        return
    topic.stage = "summary"
    await db.execute(
        update(Session)
        .where(
            Session.topic_id == topic.id,
            Session.outcome == DialogueOutcome.OPEN.value,
        )
        .values(outcome=DialogueOutcome.CLOSED_BY_SUMMARY.value)
    )


async def _mark_ready(db: AsyncSession, attempt_id: UUID, draft: dict) -> None:
    await db.execute(
        update(SummaryAttempt)
        .where(
            SummaryAttempt.id == attempt_id,
            SummaryAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(status=GenerationStatus.READY.value, result_json=draft)
    )


async def store_ready_summary(
    db: AsyncSession,
    *,
    attempt_id: UUID,
    topic_id: UUID,
    draft: dict,
) -> None:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        return
    db.add(_draft_row(topic_id, await next_version(db, topic_id), draft))
    await _close_open_dialogues(db, topic)
    await _mark_ready(db, attempt_id, draft)


async def latest_summary(db: AsyncSession, topic_id: UUID) -> ClassSummary | None:
    statement = (
        select(ClassSummary)
        .where(ClassSummary.topic_id == topic_id)
        .order_by(ClassSummary.version.desc())
        .limit(1)
    )
    return await db.scalar(statement)


async def published(db: AsyncSession, topic_id: UUID) -> PublishedSummary | None:
    return await db.get(PublishedSummary, topic_id)


async def save_published(
    db: AsyncSession, *, topic_id: UUID, version: int, body: dict
) -> None:
    row = await db.get(PublishedSummary, topic_id)
    if row is None:
        db.add(PublishedSummary(topic_id=topic_id, version=version, body=body))
        return
    row.version = version
    row.body = body


async def clear_published(db: AsyncSession, topic_id: UUID) -> bool:
    row = await db.get(PublishedSummary, topic_id)
    if row is None:
        return False
    await db.delete(row)
    return True
