"""Execute the ending migration in a disposable transactional Postgres schema."""

import asyncio
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


def test_ending_migration_backfill_and_safe_downgrade():
    url = os.environ.get("SESSION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SESSION_TEST_DATABASE_URL to execute the migration")
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/2026_11_21_1200-8ad603f2c910_add_report_eligible_ending.py"
    )
    spec = importlib.util.spec_from_file_location("ending_migration_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async def run():
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                transaction = await conn.begin()
                try:
                    schema = "ending_test_" + uuid4().hex
                    await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                    await conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                    await conn.execute(
                        text("""CREATE TABLE sessions (
                        outcome varchar(32) NOT NULL,
                        completed_at timestamptz,
                        CONSTRAINT ck_sessions_outcome CHECK
                        (outcome IN ('open', 'completed', 'abandoned', 'closed_by_summary'))
                    )""")
                    )
                    await conn.execute(
                        text(
                            "INSERT INTO sessions VALUES ('completed', CURRENT_TIMESTAMP)"
                        )
                    )

                    def migrate(sync_conn, direction):
                        module.op = Operations(MigrationContext.configure(sync_conn))
                        getattr(module, direction)()

                    await conn.run_sync(migrate, "upgrade")
                    row = (
                        await conn.execute(
                            text(
                                "SELECT ended_at = completed_at, ending_reason FROM sessions"
                            )
                        )
                    ).one()
                    assert row == (True, "goal_reached")
                    await conn.execute(
                        text(
                            "INSERT INTO sessions (outcome, ending_reason) VALUES ('ended', 'turn_limit')"
                        )
                    )
                    with pytest.raises(
                        DBAPIError, match="Cannot downgrade while ended dialogues exist"
                    ):
                        async with conn.begin_nested():
                            await conn.run_sync(migrate, "downgrade")
                    await conn.execute(
                        text("DELETE FROM sessions WHERE outcome = 'ended'")
                    )
                    await conn.run_sync(migrate, "downgrade")
                    with pytest.raises(DBAPIError):
                        async with conn.begin_nested():
                            await conn.execute(
                                text("INSERT INTO sessions (outcome) VALUES ('ended')")
                            )
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(run())
