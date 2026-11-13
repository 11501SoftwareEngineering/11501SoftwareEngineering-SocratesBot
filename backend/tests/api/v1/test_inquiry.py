"""Inquiry setup API tests. Generation uses a stub and never calls OpenAI."""

from __future__ import annotations

import logging
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
        "version": 1,
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
    monkeypatch.setattr(settings, "OPENAI_API_KEY", type(settings.OPENAI_API_KEY)(KEY))
    return recorded


def test_publish_rejects_blank_topic_and_bad_age(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(
        inquiry_topic="   ",
        core_question="Why?",
        age_band="13-15",
        max_turns=10,
    )
    _ready(monkeypatch, topic)

    missing_topic = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
    )
    assert missing_topic.status_code == 409
    assert missing_topic.json()["detail"] == "Incomplete setup: topic"
    assert topic.stage == "setup"

    topic.inquiry_topic = "Cities"
    topic.age_band = None
    bad_age = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
    )
    assert bad_age.status_code == 409
    assert bad_age.json()["detail"] == "Incomplete setup: age_band"
    rejected = auth_client.put(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
        json={"setup": {"age_band": "18+", "topic": "Cities", "core_question": "Why?"}},
    )
    assert rejected.status_code == 422
    assert topic.stage == "setup"

    topic.age_band = "18+"
    topic.inquiry_topic = "Cities"
    topic.core_question = "Why?"
    topic.max_turns = 10
    illegal_age = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
    )
    assert illegal_age.status_code == 409
    assert illegal_age.json()["detail"] == "Incomplete setup: age_band"
    assert topic.stage == "setup"
    course_route_db.commit.assert_not_awaited()


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
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    _ready(monkeypatch, topic, instructor_id=teacher.id)

    ready = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
    )
    assert ready.status_code == 200
    assert ready.json()["setup"]["topic"] == "saved topic"
    assert "version" not in ready.json()
    denied = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": outsider_bearer},
    )
    assert denied.status_code == 403


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
        json={"feedback": DIALOGUE},
    )
    assert response.status_code == 503
    assert topic.inquiry_topic == "saved topic"
    recorded.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()
    assert KEY not in caplog.text
    assert DIALOGUE not in caplog.text
    assert DIALOGUE not in response.text


def test_opening_message_is_not_stored(
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
        return GENERATED

    monkeypatch.setattr(OpenAIChatClient, "complete_json", complete)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/opening-message",
        headers={"Authorization": bearer},
        json={"setup": {"topic": "Cities", "core_question": "Why?"}},
    )
    assert response.status_code == 200
    assert response.json() == {"opening_message": "Where should we start?"}
    assert topic.opening_message is None
    recorded.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()
