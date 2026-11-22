"""save_exchange must lock the session row before it writes progress."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.crud import message as message_crud

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_row_lock_is_taken_before_the_progress_update() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = MagicMock()
    db.execute.return_value = result

    await message_crud.save_exchange(
        db,
        session_id=uuid4(),
        content="student",
        request_id=uuid4(),
        reply="assistant",
        goal_reached=False,
        prompt_stage="dialogue",
        prompt_version="stage2_planing-1.0.0",
        analysis={"move": "elicit_reason"},
        progress={"stalledTurns": 0},
    )

    statements = [call.args[0] for call in db.execute.await_args_list]
    first = str(statements[0].compile(dialect=postgresql.dialect()))
    last = str(statements[-1].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in first
    assert "UPDATE sessions" in last
