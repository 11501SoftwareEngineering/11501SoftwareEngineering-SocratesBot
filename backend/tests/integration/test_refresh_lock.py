"""Concurrency tests for refresh rotation ``SELECT … FOR UPDATE``."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.enums import UserRole
from app.core.migration import run_migrations
from app.core.security import hash_password, hash_token
from app.crud.auth import (
    RenewOutcome,
    create_refresh_token,
    renew_with_lock,
)
from app.models.user import RefreshToken, User, UserPassword


async def _seed_user_with_refresh() -> tuple[uuid.UUID, str]:
    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        user = User(
            id=user_id,
            account_id=f"lock-{user_id.hex[:8]}",
            name="Lock Test",
            role=UserRole.USER.value,
        )
        user.password = UserPassword(
            password_hash=hash_password("password1"),
            must_change_password=False,
        )
        db.add(user)
        await db.commit()
        raw = await create_refresh_token(db, user_id)
    return user_id, raw


async def _assert_active_count(user_id: uuid.UUID, expected: int) -> None:
    async with AsyncSessionLocal() as db:
        active = await db.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    assert active == expected


@pytest.mark.integration
def test_refresh_lock_concurrent_and_post_grace_theft() -> None:
    """One event loop: concurrent ACCESS_ONLY, then post-grace revoke-all."""

    async def _run() -> None:
        await run_migrations()
        user_id, raw = await _seed_user_with_refresh()

        results = await asyncio.gather(
            renew_with_lock(raw),
            renew_with_lock(raw),
        )
        outcomes = {r.outcome for r in results}
        assert RenewOutcome.ROTATED in outcomes
        assert RenewOutcome.REJECTED not in outcomes
        assert outcomes <= {RenewOutcome.ROTATED, RenewOutcome.ACCESS_ONLY}
        await _assert_active_count(user_id, 1)

        user_id2, raw2 = await _seed_user_with_refresh()
        first = await renew_with_lock(raw2)
        assert first.outcome is RenewOutcome.ROTATED

        past = datetime.now(UTC) - timedelta(
            seconds=settings.REFRESH_REUSE_GRACE_SECONDS + 1
        )
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.token_hash == hash_token(raw2))
                .values(revoked_at=past)
            )
            await db.commit()

        second = await renew_with_lock(raw2)
        assert second.outcome is RenewOutcome.REJECTED
        await _assert_active_count(user_id2, 0)

    asyncio.run(_run())
