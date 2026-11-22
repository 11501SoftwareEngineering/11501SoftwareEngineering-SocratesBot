from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.crud import message as message_crud
from app.crud import report as report_crud
from app.crud import summary as summary_crud
from app.models.message import DialogueMessage

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_exchange_stores_prompt_metadata_on_assistant_only() -> None:
    db = AsyncMock()

    await message_crud.save_exchange(
        db,
        session_id=uuid4(),
        content="student message",
        request_id=uuid4(),
        reply="assistant reply",
        goal_reached=False,
        prompt_stage="dialogue",
        prompt_version="v1",
    )

    student, assistant = [call.args[0] for call in db.add.call_args_list]
    assert isinstance(student, DialogueMessage)
    assert student.sender == "student"
    assert student.generation_meta is None
    assert assistant.sender == "ai"
    assert assistant.generation_meta == {
        "prompt_stage": "dialogue",
        "prompt_version": "v1",
    }
    db.flush.assert_awaited_once()


async def test_ready_report_and_summary_store_prompt_metadata() -> None:
    db = AsyncMock()

    await report_crud.mark_ready(
        db,
        uuid4(),
        {"viewpoint_summary": "supported"},
        prompt_stage="personal_report",
        prompt_version="v1",
    )
    report_statement = db.execute.await_args.args[0]
    report_values = report_statement.compile().params
    assert {
        "prompt_stage": "personal_report",
        "prompt_version": "v1",
    } in report_values.values()

    db.reset_mock()
    await summary_crud._mark_ready(
        db,
        uuid4(),
        {"overview": "supported"},
        prompt_stage="class_summary",
        prompt_version="v1",
    )
    summary_statement = db.execute.await_args.args[0]
    summary_values = summary_statement.compile().params
    assert {
        "prompt_stage": "class_summary",
        "prompt_version": "v1",
    } in summary_values.values()
