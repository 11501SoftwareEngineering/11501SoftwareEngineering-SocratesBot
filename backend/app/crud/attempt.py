"""Storage for generation attempts. Rows do not store provider keys or bodies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GenerationStatus
from app.models.generation_attempt import INQUIRY_FIELDS, GenerationAttempt


async def create_inquiry_attempt(
    db: AsyncSession,
    *,
    topic_id: UUID,
    request_json: dict,
) -> GenerationAttempt:
    attempt = GenerationAttempt(
        topic_id=topic_id,
        kind=INQUIRY_FIELDS,
        status=GenerationStatus.PENDING.value,
        request_json=request_json,
    )
    db.add(attempt)
    await db.flush()
    return attempt


async def get_attempt(db: AsyncSession, attempt_id: UUID) -> GenerationAttempt | None:
    return await db.get(GenerationAttempt, attempt_id)


async def latest_inquiry_attempt(
    db: AsyncSession, topic_id: UUID
) -> GenerationAttempt | None:
    statement = (
        select(GenerationAttempt)
        .where(
            GenerationAttempt.topic_id == topic_id,
            GenerationAttempt.kind == INQUIRY_FIELDS,
        )
        .order_by(GenerationAttempt.created_at.desc(), GenerationAttempt.id.desc())
        .limit(1)
    )
    return await db.scalar(statement)


async def mark_processing(db: AsyncSession, attempt_id: UUID) -> None:
    await db.execute(
        update(GenerationAttempt)
        .where(
            GenerationAttempt.id == attempt_id,
            GenerationAttempt.status == GenerationStatus.PENDING.value,
        )
        .values(status=GenerationStatus.PROCESSING.value)
    )


async def refresh_lease(db: AsyncSession, attempt_id: UUID, *, seconds: int) -> None:
    expires = datetime.now(UTC) + timedelta(seconds=seconds)
    await db.execute(
        update(GenerationAttempt)
        .where(
            GenerationAttempt.id == attempt_id,
            GenerationAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(lease_expires_at=expires)
    )


async def mark_ready_if_processing(
    db: AsyncSession, attempt_id: UUID, result_json: dict
) -> bool:
    result = await db.execute(
        update(GenerationAttempt)
        .where(
            GenerationAttempt.id == attempt_id,
            GenerationAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(
            status=GenerationStatus.READY.value,
            result_json=result_json,
            lease_expires_at=None,
        )
    )
    return result.rowcount == 1


async def mark_failed_if_processing(db: AsyncSession, attempt_id: UUID) -> bool:
    result = await db.execute(
        update(GenerationAttempt)
        .where(
            GenerationAttempt.id == attempt_id,
            GenerationAttempt.status == GenerationStatus.PROCESSING.value,
        )
        .values(status=GenerationStatus.FAILED.value, lease_expires_at=None)
    )
    return result.rowcount == 1


async def list_processing(db: AsyncSession) -> list[GenerationAttempt]:
    statement = select(GenerationAttempt).where(
        GenerationAttempt.status == GenerationStatus.PROCESSING.value
    )
    result = await db.scalars(statement)
    return list(result.all())
