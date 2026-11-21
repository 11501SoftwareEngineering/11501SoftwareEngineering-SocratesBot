"""Model calls in a course use the course teacher's key, else the server pool."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.session import Session
from app.models.topic import Topic
from app.services import dialogue, report_runner, summary_runner
from app.services import teacher_ai_settings as ai_settings
from app.services.model_client import ModelCallError

pytestmark = pytest.mark.anyio

TEACHER_KEY = "sk-or-course-teacher"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _Sessions:
    """Stands in for AsyncSessionLocal: each call yields the same fake db."""

    def __init__(self, db: object) -> None:
        self.db = db

    def __call__(self) -> _Sessions:
        return self

    async def __aenter__(self) -> object:
        return self.db

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _RecordingClient:
    def __init__(self) -> None:
        self.keys: list[str | None] = []

    async def complete_object(self, *, api_key=None, **_kwargs):
        self.keys.append(api_key)
        raise ModelCallError(503)


def _topic(course_id=None) -> Topic:
    return Topic(
        id=uuid4(),
        course_id=course_id or uuid4(),
        created_by=uuid4(),
        title="Course",
        stage="conversation",
        max_turns=None,
    )


# course_api_key


async def test_course_key_is_the_course_teachers_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course = SimpleNamespace(id=uuid4(), created_by=uuid4())
    monkeypatch.setattr(
        ai_settings.course_crud, "get_course_by_id", AsyncMock(return_value=course)
    )
    lookup = AsyncMock(return_value=TEACHER_KEY)
    monkeypatch.setattr(ai_settings, "teacher_api_key", lookup)

    assert await ai_settings.course_api_key(object(), course.id) == TEACHER_KEY
    lookup.assert_awaited_once()
    assert lookup.await_args.args[1] == course.created_by


async def test_course_key_is_none_without_a_teacher_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course = SimpleNamespace(id=uuid4(), created_by=uuid4())
    monkeypatch.setattr(
        ai_settings.course_crud, "get_course_by_id", AsyncMock(return_value=course)
    )
    monkeypatch.setattr(
        ai_settings.settings_crud, "get_settings", AsyncMock(return_value=None)
    )

    assert await ai_settings.course_api_key(object(), course.id) is None


async def test_course_key_is_none_for_a_missing_course(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_settings.course_crud, "get_course_by_id", AsyncMock(return_value=None)
    )

    assert await ai_settings.course_api_key(object(), uuid4()) is None


# Student dialogue


@pytest.mark.parametrize("course_key", [TEACHER_KEY, None])
async def test_student_reply_uses_the_course_key(
    monkeypatch: pytest.MonkeyPatch, course_key: str | None
) -> None:
    topic = _topic()
    session = Session(
        id=uuid4(),
        topic_id=topic.id,
        user_id=uuid4(),
        outcome="open",
        awaiting_end_consent=False,
    )
    monkeypatch.setattr(
        dialogue, "_owned", AsyncMock(return_value=(session, topic, []))
    )
    key_lookup = AsyncMock(return_value=course_key)
    monkeypatch.setattr(dialogue, "course_api_key", key_lookup)
    done = object()
    ask = AsyncMock(return_value=done)
    monkeypatch.setattr(dialogue, "_ask_and_store", ask)

    result = await dialogue.send_reply(
        AsyncMock(),
        _RecordingClient(),
        user_id=session.user_id,
        session_id=session.id,
        content="I think so",
        request_id=uuid4(),
    )

    # Each stage sends this key; see test_dialogue_turn and test_dialogue_context.
    assert result is done
    assert ask.await_args.kwargs["api_key"] == course_key
    assert key_lookup.await_args.args[1] == topic.course_id


async def test_unreadable_teacher_key_stops_the_reply_before_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topic = _topic()
    session = Session(id=uuid4(), topic_id=topic.id, user_id=uuid4(), outcome="open")
    monkeypatch.setattr(
        dialogue, "_owned", AsyncMock(return_value=(session, topic, []))
    )
    unreadable = HTTPException(status_code=503, detail="Teacher API key cannot be read")
    monkeypatch.setattr(dialogue, "course_api_key", AsyncMock(side_effect=unreadable))
    ask = AsyncMock()
    monkeypatch.setattr(dialogue, "_ask_and_store", ask)

    with pytest.raises(HTTPException) as caught:
        await dialogue.send_reply(
            AsyncMock(),
            _RecordingClient(),
            user_id=session.user_id,
            session_id=session.id,
            content="I think so",
            request_id=uuid4(),
        )

    assert caught.value.status_code == 503
    ask.assert_not_awaited()
    # The session is not left marked busy.
    assert session.id not in dialogue._BUSY


# Personal report


async def test_report_material_comes_with_the_course_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topic = _topic()
    session = SimpleNamespace(id=uuid4(), topic_id=topic.id, user_id=uuid4())
    rows = {Session: session, Topic: topic}
    db = SimpleNamespace(get=AsyncMock(side_effect=lambda model, _id: rows[model]))
    monkeypatch.setattr(report_runner, "AsyncSessionLocal", _Sessions(db))
    monkeypatch.setattr(
        report_runner.message_crud, "load_owned_dialogue", AsyncMock(return_value=None)
    )
    key_lookup = AsyncMock(return_value=TEACHER_KEY)
    monkeypatch.setattr(report_runner, "course_api_key", key_lookup)

    material, api_key = await report_runner._prepare(session.id, None)

    assert "progressSnapshot:\nnull" in material
    assert api_key == TEACHER_KEY
    assert key_lookup.await_args.args[1] == topic.course_id


async def _no_lease(*_args: object) -> None:
    return None


@pytest.mark.parametrize("course_key", [TEACHER_KEY, None])
async def test_report_call_uses_the_course_key(
    monkeypatch: pytest.MonkeyPatch, course_key: str | None
) -> None:
    attempt_id = uuid4()
    client = _RecordingClient()
    failed = AsyncMock()
    monkeypatch.setattr(report_runner, "client", client)
    monkeypatch.setattr(report_runner, "refresh", _no_lease)
    monkeypatch.setattr(
        report_runner, "_begin", AsyncMock(return_value=(uuid4(), None))
    )
    monkeypatch.setattr(
        report_runner, "_prepare", AsyncMock(return_value=("material", course_key))
    )
    monkeypatch.setattr(report_runner, "_fail", failed)

    await report_runner.run_report(attempt_id)

    assert client.keys == [course_key]
    failed.assert_awaited_once_with(attempt_id)


async def test_unreadable_teacher_key_fails_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt_id = uuid4()
    client = _RecordingClient()
    failed = AsyncMock()
    unreadable = HTTPException(status_code=503, detail="Teacher API key cannot be read")
    monkeypatch.setattr(report_runner, "client", client)
    monkeypatch.setattr(report_runner, "refresh", _no_lease)
    monkeypatch.setattr(
        report_runner, "_begin", AsyncMock(return_value=(uuid4(), None))
    )
    monkeypatch.setattr(report_runner, "_prepare", AsyncMock(side_effect=unreadable))
    monkeypatch.setattr(report_runner, "_fail", failed)

    await report_runner.run_report(attempt_id)

    assert client.keys == []
    failed.assert_awaited_once_with(attempt_id)


# Class summary


async def test_summary_key_is_the_course_key_of_the_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topic = _topic()
    monkeypatch.setattr(summary_runner, "AsyncSessionLocal", _Sessions(object()))
    monkeypatch.setattr(
        summary_runner.topic_crud, "get_topic_by_id", AsyncMock(return_value=topic)
    )
    key_lookup = AsyncMock(return_value=TEACHER_KEY)
    monkeypatch.setattr(summary_runner, "course_api_key", key_lookup)

    assert await summary_runner._api_key(topic.id) == TEACHER_KEY
    assert key_lookup.await_args.args[1] == topic.course_id


@pytest.mark.parametrize("course_key", [TEACHER_KEY, None])
async def test_summary_call_uses_the_course_key(
    monkeypatch: pytest.MonkeyPatch, course_key: str | None
) -> None:
    attempt_id = uuid4()
    client = _RecordingClient()
    failed = AsyncMock()
    request = {"topic_id": uuid4(), "material": {}, "labels": []}
    monkeypatch.setattr(summary_runner, "client", client)
    monkeypatch.setattr(summary_runner, "refresh", _no_lease)
    monkeypatch.setattr(summary_runner, "_begin", AsyncMock(return_value=request))
    monkeypatch.setattr(summary_runner, "_api_key", AsyncMock(return_value=course_key))
    monkeypatch.setattr(summary_runner, "_fail", failed)

    await summary_runner.run_summary(attempt_id)

    assert client.keys == [course_key]
    failed.assert_awaited_once_with(attempt_id)
