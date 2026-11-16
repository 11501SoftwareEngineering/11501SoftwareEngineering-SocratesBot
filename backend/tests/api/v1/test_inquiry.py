"""Inquiry setup API tests. Generation uses a stub and never calls OpenAI."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.enums import UserRole
from app.crud import course as course_crud
from app.crud import topic as topic_crud
from app.services.model_client import ModelCallError, OpenAIChatClient
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user

KEY = "sk-test-do-not-leak"
DIALOGUE = "dialogue-do-not-leak"
GENERATED = {
    "age_band": "16-18",
    "max_turns": 10,
    "topic": "generated topic",
    "core_question": "generated question",
    "inquiry_focus": "compare the two accounts",
    "background_info": "a published case",
    "exclusions": "unspecified",
    "opening_message": "Where should we start?",
}


def _login(client: TestClient, store: FakeStore, account: str = "teacher1"):
    user = seed_user(store, account_id=account, role=UserRole.TEACHER)
    response = client.post(
        "/api/v1/auth/login",
        json={"account_id": account, "password": "password1"},
    )
    assert response.status_code == 200
    return bearer_from(response), user


def _topic(**overrides) -> SimpleNamespace:
    values = {
        "id": uuid4(),
        "course_id": uuid4(),
        "stage": "setup",
        "content_language": None,
        "model_id": "openai/gpt-4o-mini",
        "age_band": None,
        "max_turns": None,
        "inquiry_topic": None,
        "core_question": None,
        "inquiry_focus": None,
        "background_info": None,
        "exclusions": None,
        "opening_message": None,
        "updated_at": datetime(2026, 11, 16, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _ready(monkeypatch: pytest.MonkeyPatch, topic, *, instructor_id=None) -> AsyncMock:
    monkeypatch.setattr("app.crud.topic.get_topic_by_id", AsyncMock(return_value=topic))
    recorded = AsyncMock()
    monkeypatch.setattr(topic_crud, "record_inquiry_change", recorded)

    async def is_instructor(_db, *, course_id, teacher_id):
        assert course_id == topic.course_id
        if instructor_id is None:
            return True
        return teacher_id == instructor_id

    monkeypatch.setattr(course_crud, "is_course_instructor", is_instructor)
    monkeypatch.setattr(topic_crud, "lock_topic", AsyncMock(return_value=topic))
    monkeypatch.setattr(settings, "OPENAI_API_KEY", type(settings.OPENAI_API_KEY)(KEY))
    return recorded


def test_publish_stores_the_screen_and_rejects_an_incomplete_one(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="old topic", core_question="old question")
    recorded = _ready(monkeypatch, topic)

    missing_topic = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
        json={
            "setup": {
                "age_band": "13-15",
                "max_turns": 10,
                "core_question": "Why?",
            }
        },
    )
    assert missing_topic.status_code == 422
    assert missing_topic.json()["detail"] == "Incomplete setup: topic"
    assert topic.stage == "setup"

    missing_age = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
        json={
            "setup": {
                "max_turns": 10,
                "topic": "Cities",
                "core_question": "Why?",
            }
        },
    )
    assert missing_age.status_code == 422
    assert missing_age.json()["detail"] == "Incomplete setup: age_band"

    illegal_age = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
        json={
            "setup": {
                "age_band": "18+",
                "max_turns": 10,
                "topic": "Cities",
                "core_question": "Why?",
            }
        },
    )
    assert illegal_age.status_code == 422
    assert topic.stage == "setup"
    course_route_db.commit.assert_not_awaited()

    published = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
        json={
            "setup": {
                "age_band": "university_plus",
                "max_turns": 5,
                "topic": "Cities",
                "core_question": "Who maintains them?",
                "inquiry_focus": "the public cost",
            }
        },
    )
    assert published.status_code == 200
    body = published.json()
    assert "opening_message" not in body
    assert body["setup"]["topic"] == "Cities"
    assert topic.stage == "conversation"
    assert topic.inquiry_topic == "Cities"
    assert topic.title == "Cities"
    assert topic.core_question == "Who maintains them?"
    assert topic.description == "Who maintains them?"
    assert topic.age_band == "university_plus"
    recorded.assert_awaited()
    course_route_db.commit.assert_awaited()


def test_save_stores_fields_without_returning_a_version(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic()
    recorded = _ready(monkeypatch, topic)

    response = auth_client.put(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
        json={
            "setup": {
                "age_band": "university_plus",
                "max_turns": 5,
                "topic": "Cities",
                "core_question": "Who maintains them?",
                "inquiry_focus": "the public cost",
                "opening_message": "",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["setup"]["topic"] == "Cities"
    assert "opening_message" not in body["setup"]
    assert "version" not in body
    assert topic.opening_message is None
    assert topic.inquiry_topic == "Cities"
    assert topic.title == "Cities"
    assert topic.core_question == "Who maintains them?"
    assert topic.description == "Who maintains them?"
    assert topic.exclusions == "unspecified"
    assert topic.stage == "setup"
    recorded.assert_awaited_once()
    course_route_db.commit.assert_awaited()


def test_get_setup_is_instructor_only(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login(auth_client, store)
    outsider_bearer, _ = _login(auth_client, store, account="outsider")
    topic = _topic(
        inquiry_topic="saved topic",
        core_question="saved question",
        opening_message="Hello",
    )
    _ready(monkeypatch, topic, instructor_id=teacher.id)

    ready = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
    )
    assert ready.status_code == 200
    body = ready.json()
    assert body["setup"]["topic"] == "saved topic"
    assert body["setup"]["opening_message"] == "Hello"
    assert "opening_message" not in body
    assert "version" not in body
    denied = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": outsider_bearer},
    )
    assert denied.status_code == 403


def test_refine_uses_the_screen_setup(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    _ready(monkeypatch, topic)
    seen: dict[str, str] = {}

    async def complete(
        self, *, instructions: str, material: str, model: str | None = None
    ):
        seen["material"] = material
        return GENERATED

    monkeypatch.setattr(OpenAIChatClient, "complete_json", complete)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/refine",
        headers={"Authorization": bearer},
        json={
            "feedback": "shorter",
            "setup": {
                "topic": "edited on screen",
                "core_question": "Why now?",
                "age_band": "16-18",
                "max_turns": 10,
            },
        },
    )

    assert response.status_code == 200
    assert "edited on screen" in seen["material"]
    assert "saved topic" not in seen["material"]
    assert "shorter" in seen["material"]
    body = response.json()
    assert "opening_message" not in body
    assert body["setup"]["opening_message"] == "Where should we start?"
    assert topic.inquiry_topic == "generated topic"
    assert topic.title == "generated topic"
    assert topic.description == "generated question"
    course_route_db.commit.assert_awaited()


def test_failed_regeneration_keeps_the_saved_inquiry(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    recorded = _ready(monkeypatch, topic)

    async def fail(self, *, instructions: str, material: str, model: str | None = None):
        raise ModelCallError(503)

    monkeypatch.setattr(OpenAIChatClient, "complete_json", fail)
    caplog.set_level(logging.INFO)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/refine",
        headers={"Authorization": bearer},
        json={
            "feedback": DIALOGUE,
            "setup": {"topic": "unsaved edit", "core_question": "saved question"},
        },
    )
    assert response.status_code == 503
    assert topic.inquiry_topic == "saved topic"
    recorded.assert_not_awaited()
    assert KEY not in caplog.text
    assert DIALOGUE not in caplog.text
    assert DIALOGUE not in response.text


def test_opening_message_is_stored(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(opening_message=None)
    recorded = _ready(monkeypatch, topic)

    async def complete(
        self, *, instructions: str, material: str, model: str | None = None
    ):
        return {**GENERATED, "topic": "  ", "core_question": ""}

    monkeypatch.setattr(OpenAIChatClient, "complete_json", complete)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/opening-message",
        headers={"Authorization": bearer},
        json={"setup": {"topic": "Cities", "core_question": "Why?"}},
    )
    assert response.status_code == 200
    assert response.json() == {"opening_message": "Where should we start?"}
    assert topic.opening_message == "Where should we start?"
    assert topic.inquiry_topic is None
    recorded.assert_awaited_once()
    course_route_db.commit.assert_awaited()


def test_refine_stops_when_publish_lands_first(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    recorded = _ready(monkeypatch, topic)

    async def published(_db, topic_id):
        topic.stage = "conversation"
        return topic

    monkeypatch.setattr(topic_crud, "lock_topic", published)

    async def complete(
        self, *, instructions: str, material: str, model: str | None = None
    ):
        return GENERATED

    monkeypatch.setattr(OpenAIChatClient, "complete_json", complete)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/refine",
        headers={"Authorization": bearer},
        json={"feedback": "shorter", "setup": {"topic": "edited on screen"}},
    )

    assert response.status_code == 400
    assert topic.inquiry_topic == "saved topic"
    recorded.assert_not_awaited()


def test_overlong_model_text_is_not_stored(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    recorded = _ready(monkeypatch, topic)

    async def complete(
        self, *, instructions: str, material: str, model: str | None = None
    ):
        return {**GENERATED, "background_info": "x" * 8001}

    monkeypatch.setattr(OpenAIChatClient, "complete_json", complete)
    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/refine",
        headers={"Authorization": bearer},
        json={"feedback": "expand", "setup": {"topic": "saved topic"}},
    )

    assert response.status_code == 502
    assert topic.inquiry_topic == "saved topic"
    assert topic.background_info is None
    recorded.assert_not_awaited()


def test_refine_refuses_a_save_that_landed_while_the_model_ran(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    recorded = _ready(monkeypatch, topic)
    seen = topic.updated_at

    async def newer(_db, _topic_id):
        topic.updated_at = seen + timedelta(seconds=1)
        return topic

    monkeypatch.setattr(topic_crud, "lock_topic", newer)

    async def complete(
        self, *, instructions: str, material: str, model: str | None = None
    ):
        return GENERATED

    monkeypatch.setattr(OpenAIChatClient, "complete_json", complete)
    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/refine",
        headers={"Authorization": bearer},
        json={"feedback": "shorter", "setup": {"topic": "saved topic"}},
    )

    assert response.status_code == 409
    assert topic.inquiry_topic == "saved topic"
    recorded.assert_not_awaited()
