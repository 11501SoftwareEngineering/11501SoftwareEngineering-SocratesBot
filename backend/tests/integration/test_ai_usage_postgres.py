"""Real persistence, UTC/teacher isolation and independent transaction durability."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.enums import UserRole
from app.models.user import User
from app.services import ai_usage

pytestmark = pytest.mark.integration


def test_usage_survives_business_rollback_and_is_teacher_month_scoped(monkeypatch):
    async def run():
        url = os.environ.get("SESSION_TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set SESSION_TEST_DATABASE_URL for disposable Postgres")
        engine = create_async_engine(url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        owner, outsider = uuid4(), uuid4()
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with factory() as db:
                for ident in (owner, outsider):
                    db.add(
                        User(
                            id=ident,
                            account_id="usage-" + ident.hex,
                            name="Synthetic usage",
                            role=UserRole.TEACHER.value,
                        )
                    )
                await db.commit()
            monkeypatch.setattr(ai_usage, "AsyncSessionLocal", factory)
            key = ai_usage.AttributedKey("sk-test-not-real", owner, "server")
            async with factory() as business:
                # The reader/request transaction is later rolled back; ledger owns its connection.
                await business.get(User, owner)
                event = await ai_usage.begin(key, "dialogue_status", "test-model")
                await ai_usage.finish(
                    event,
                    httpx.Response(
                        200,
                        json={
                            "usage": {
                                "prompt_tokens": 11,
                                "completion_tokens": 1000,
                                "total_tokens": 1011,
                                "cost": 0.003,
                            }
                        },
                    ),
                )
                await business.rollback()
            async with factory() as db:
                body = await ai_usage.read_month(db, owner)
                assert body.request_count == 1 and body.total_tokens == 1011
                assert body.cost_usd == pytest.approx(0.003)
                assert (await ai_usage.read_month(db, outsider)).request_count == 0
                assert (
                    await ai_usage.read_month(
                        db, owner, now=datetime(2020, 1, 1, tzinfo=UTC)
                    )
                ).request_count == 0
            pending = await ai_usage.begin(key, "personal_report", "test-model")
            async with factory() as db:
                body = await ai_usage.read_month(db, owner)
                assert (
                    body.request_count == 2
                    and body.total_tokens is None
                    and body.cost_usd is None
                )
            await ai_usage.finish(
                pending,
                httpx.Response(
                    200,
                    json={
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 2,
                            "total_tokens": 3,
                            "cost": 0,
                        }
                    },
                ),
            )
            async with factory() as db:
                body = await ai_usage.read_month(db, owner)
                assert body.total_tokens == 1014 and body.by_stage[2].cost_usd == 0
        finally:
            async with factory() as db:
                await db.execute(delete(User).where(User.id.in_((owner, outsider))))
                await db.commit()
            await engine.dispose()

    asyncio.run(run())
