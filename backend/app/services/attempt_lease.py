"""A processing attempt stays up only while its task refreshes the lease.

A status read does not fail anything. Startup fails processing rows this
process is not running. Afterwards only a missing or passed lease does.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.enums import GenerationStatus

logger = logging.getLogger("app.model")
LEASE = timedelta(seconds=30)
REFRESH_SECONDS = 10

ListProcessing = Callable[[AsyncSession], Awaitable[list]]


def should_fail(
    lease: datetime | None,
    now: datetime,
    *,
    live: bool,
    startup: bool,
) -> bool:
    """Return whether this processing row should be stored as failed."""
    if live:
        return False
    if startup:
        return True
    return lease is None or lease < now


async def refresh(
    extend: Callable[[AsyncSession, UUID], Awaitable[None]],
    attempt_id: UUID,
    live: set[UUID],
) -> None:
    """Push the lease forward until the attempt leaves the live set."""
    while True:
        await asyncio.sleep(REFRESH_SECONDS)
        if attempt_id not in live:
            return
        async with AsyncSessionLocal() as db:
            await extend(db, attempt_id)
            await db.commit()


def _pairs() -> list[tuple[ListProcessing, set[UUID]]]:
    from app.crud import report as report_crud
    from app.services.report_runner import live_attempts

    pairs: list[tuple[ListProcessing, set[UUID]]] = [
        (report_crud.list_processing, live_attempts())
    ]
    try:
        from app.crud import summary as summary_crud
        from app.services.summary_runner import live_attempts as summary_live
    except ImportError:
        return pairs
    pairs.append((summary_crud.list_processing, summary_live()))
    return pairs


async def reclaim_open_attempts(*, startup: bool) -> None:
    """Fail processing attempts whose lease is no longer held."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        changed = False
        for list_processing, live in _pairs():
            for row in await list_processing(db):
                if should_fail(
                    row.lease_expires_at,
                    now,
                    live=row.id in live,
                    startup=startup,
                ):
                    row.status = GenerationStatus.FAILED.value
                    changed = True
        if changed:
            await db.commit()


async def watch_leases() -> None:
    """Keep failing attempts after the task that held them has stopped."""
    while True:
        await asyncio.sleep(REFRESH_SECONDS)
        try:
            await reclaim_open_attempts(startup=False)
        except Exception:
            logger.info("attempt lease sweep failed")
