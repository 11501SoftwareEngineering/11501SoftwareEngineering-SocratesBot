from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Integer, cast, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogueOutcome, GenerationStatus
from app.models.class_summary import ClassSummary, SummaryAttempt
from app.models.report_attempt import ReportAttempt
from app.models.session import Session
from app.models.topic import Topic
from app.services.attempt_lease import LEASE


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
            lease_expires_at=datetime.now(UTC) + LEASE,
        )
    )


async def extend_lease(db: AsyncSession, attempt_id: UUID) -> None:
    await db.execute(
        update(SummaryAttempt)
        .where(
            SummaryAttempt.id == attempt_id,
            SummaryAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(lease_expires_at=datetime.now(UTC) + LEASE)
    )


async def list_processing(db: AsyncSession) -> list[SummaryAttempt]:
    statement = select(SummaryAttempt).where(
        SummaryAttempt.status == GenerationStatus.PROCESSING.value
    )
    return list(await db.scalars(statement))


async def mark_failed(db: AsyncSession, attempt_id: UUID) -> None:
    await db.execute(
        update(SummaryAttempt)
        .where(
            SummaryAttempt.id == attempt_id,
            SummaryAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(status=GenerationStatus.FAILED.value)
    )


def _document(draft: dict, previous: dict | None) -> dict:
    kept = previous or {}
    return {
        "status": "draft",
        "overview": draft["overview"],
        "viewpoint_summary": draft["viewpoint_summary"],
        "denominator": draft["denominator"],
        "groups": draft["groups"],
        "ungrouped_report_ids": draft["ungrouped_report_ids"],
        "published": kept.get("published"),
        "published_version": kept.get("published_version"),
    }


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
    row = await latest_summary(db, topic_id)
    version = 1 if row is None else row.version + 1
    body = _document(draft, None if row is None else row.body)
    if row is None:
        db.add(ClassSummary(topic_id=topic_id, version=version, body=body))
    else:
        row.version = version
        row.body = body
    await _close_open_dialogues(db, topic)
    await _mark_ready(db, attempt_id, draft)


async def latest_summary(db: AsyncSession, topic_id: UUID) -> ClassSummary | None:
    statement = select(ClassSummary).where(ClassSummary.topic_id == topic_id)
    return await db.scalar(statement)


async def published_document(db: AsyncSession, topic_id: UUID) -> dict | None:
    statement = select(ClassSummary.body["published"]).where(
        ClassSummary.topic_id == topic_id
    )
    return await db.scalar(statement)


async def published_version(db: AsyncSession, topic_id: UUID) -> int | None:
    statement = select(
        cast(ClassSummary.body["published_version"].astext, Integer)
    ).where(ClassSummary.topic_id == topic_id)
    return await db.scalar(statement)
