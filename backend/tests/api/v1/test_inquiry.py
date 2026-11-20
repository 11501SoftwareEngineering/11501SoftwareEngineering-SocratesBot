"""Inquiry setup API tests. Generation uses a stub and never calls OpenAI."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
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
    assert topic.age_band == "university_plus"
    assert topic.max_turns == 5
    assert topic.core_question == "Who maintains them?"
    assert topic.description == "Who maintains them?"
    recorded.assert_awaited()
    course_route_db.commit.assert_awaited()

    published_again = auth_client.post(
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
    assert published_again.status_code == 400
    assert published_again.json()["detail"] == "Topic is not in setup"
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
    recorded = _ready(monkeypatch, topic)
    seen: dict[str, str] = {}

    async def complete(
        self, *, instructions: str, material: str, model: str | None = None, **_extra
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
    assert body["setup"]["topic"] == "generated topic"
    assert body["setup"]["opening_message"] == "Where should we start?"
    assert body["topic_id"] == str(topic.id)
    assert body["course_id"] == str(topic.course_id)
    assert body["topic_status"] == "setup"
    assert body["model_id"] == "openai/gpt-4o-mini"
    assert topic.inquiry_topic == "saved topic"
    assert topic.core_question == "saved question"
    recorded.assert_not_awaited()
    course_route_db.add.assert_not_called()

    saved = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
    )
    assert saved.status_code == 200
    assert saved.json()["setup"]["topic"] == "saved topic"
    assert saved.json()["model_id"] == "openai/gpt-4o-mini"


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

    async def fail(
        self, *, instructions: str, material: str, model: str | None = None, **_extra
    ):
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
        self, *, instructions: str, material: str, model: str | None = None, **_extra
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


def test_refine_rejects_a_topic_that_is_not_in_setup(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(
        stage="conversation",
        inquiry_topic="saved topic",
        core_question="saved question",
    )
    recorded = _ready(monkeypatch, topic)
    called = AsyncMock()
    monkeypatch.setattr(OpenAIChatClient, "complete_json", called)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/refine",
        headers={"Authorization": bearer},
        json={"feedback": "shorter", "setup": {"topic": "edited on screen"}},
    )

    assert response.status_code == 400
    assert topic.inquiry_topic == "saved topic"
    assert topic.stage == "conversation"
    called.assert_not_awaited()
    recorded.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


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
        self, *, instructions: str, material: str, model: str | None = None, **_extra
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


def test_generate_returns_a_suggestion_and_leaves_the_topic(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    recorded = _ready(monkeypatch, topic)
    monkeypatch.setattr(
        "app.crud.inquiry_model.get_inquiry_model",
        AsyncMock(return_value=SimpleNamespace(model_id="openai/gpt-6-luna")),
    )

    async def complete(
        self, *, instructions: str, material: str, model: str | None = None, **_extra
    ):
        assert model == "openai/gpt-6-luna"
        assert "content_language: zh-TW\n" in material
        assert "course_description:\ncourse notes" in material
        return GENERATED

    monkeypatch.setattr(OpenAIChatClient, "complete_json", complete)
    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/generate",
        headers={"Authorization": bearer},
        json={
            "age_band": "16-18",
            "max_turns": 10,
            "content_language": "zh-TW",
            "course_description": "course notes",
            "model_id": "openai/gpt-6-luna",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic_id"] == str(topic.id)
    assert body["course_id"] == str(topic.course_id)
    assert body["model_id"] == "openai/gpt-6-luna"
    assert body["topic_status"] == "setup"
    assert body["setup"]["topic"] == "generated topic"
    assert body["setup"]["core_question"] == "generated question"
    assert topic.inquiry_topic == "saved topic"
    assert topic.core_question == "saved question"
    assert topic.model_id == "openai/gpt-4o-mini"
    assert topic.content_language is None
    recorded.assert_not_awaited()
    course_route_db.add.assert_not_called()

    saved = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
    )
    assert saved.status_code == 200
    assert saved.json()["setup"]["topic"] == "saved topic"
    assert saved.json()["model_id"] == "openai/gpt-4o-mini"


def test_generate_rejects_an_unknown_model(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic()
    _ready(monkeypatch, topic)
    monkeypatch.setattr(
        "app.crud.inquiry_model.get_inquiry_model", AsyncMock(return_value=None)
    )
    called = AsyncMock()
    monkeypatch.setattr(OpenAIChatClient, "complete_json", called)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/generate",
        headers={"Authorization": bearer},
        json={
            "age_band": "16-18",
            "max_turns": 10,
            "content_language": "zh-TW",
            "course_description": "course notes",
            "model_id": "openai/missing",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid model id"
    called.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


_GENERATE = {
    "age_band": "16-18",
    "max_turns": 10,
    "content_language": "zh-TW",
    "course_description": "course notes",
    "model_id": "openai/gpt-6-luna",
}


def test_generate_missing_topic_is_not_found(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    monkeypatch.setattr("app.crud.topic.get_topic_by_id", AsyncMock(return_value=None))
    called = AsyncMock()
    monkeypatch.setattr(OpenAIChatClient, "complete_json", called)

    response = auth_client.post(
        f"/api/v1/topics/{uuid4()}/setup/generate",
        headers={"Authorization": bearer},
        json=_GENERATE,
    )

    assert response.status_code == 404
    called.assert_not_awaited()


def test_generate_is_instructor_only(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bearer, teacher = _login(auth_client, store)
    outsider_bearer, _ = _login(auth_client, store, account="outsider")
    topic = _topic(inquiry_topic="saved topic")
    _ready(monkeypatch, topic, instructor_id=teacher.id)
    called = AsyncMock()
    monkeypatch.setattr(OpenAIChatClient, "complete_json", called)

    denied = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/generate",
        headers={"Authorization": outsider_bearer},
        json=_GENERATE,
    )

    assert denied.status_code == 403
    assert topic.inquiry_topic == "saved topic"
    called.assert_not_awaited()


def test_generate_rejects_a_topic_that_is_not_in_setup(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(stage="conversation", inquiry_topic="saved topic")
    _ready(monkeypatch, topic)
    called = AsyncMock()
    monkeypatch.setattr(OpenAIChatClient, "complete_json", called)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/generate",
        headers={"Authorization": bearer},
        json=_GENERATE,
    )

    assert response.status_code == 400
    assert topic.inquiry_topic == "saved topic"
    assert topic.stage == "conversation"
    called.assert_not_awaited()


@pytest.mark.parametrize(
    "body",
    [
        {**_GENERATE, "course_description": "   "},
        {**_GENERATE, "course_description": "x" * 6001},
        {**_GENERATE, "content_language": "   "},
        {**_GENERATE, "content_language": "x" * 17},
        {**_GENERATE, "model_id": "   "},
        {**_GENERATE, "age_band": "adults"},
        {**_GENERATE, "max_turns": 7},
    ],
)
def test_generate_rejects_a_bad_body(
    body: dict,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic")
    _ready(monkeypatch, topic)
    called = AsyncMock()
    monkeypatch.setattr(OpenAIChatClient, "complete_json", called)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/generate",
        headers={"Authorization": bearer},
        json=body,
    )

    assert response.status_code == 422
    assert topic.inquiry_topic == "saved topic"
    called.assert_not_awaited()


@pytest.mark.parametrize("status_code", [502, 503])
def test_generate_maps_a_model_failure_and_leaves_the_topic(
    status_code: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    recorded = _ready(monkeypatch, topic)
    monkeypatch.setattr(
        "app.crud.inquiry_model.get_inquiry_model",
        AsyncMock(return_value=SimpleNamespace(model_id="openai/gpt-6-luna")),
    )

    async def fail(
        self, *, instructions: str, material: str, model: str | None = None, **_extra
    ):
        if status_code == 502:
            return {**GENERATED, "background_info": "x" * 8001}
        raise ModelCallError(503)

    monkeypatch.setattr(OpenAIChatClient, "complete_json", fail)
    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/generate",
        headers={"Authorization": bearer},
        json=_GENERATE,
    )

    assert response.status_code == status_code
    assert response.json()["detail"] == "Inquiry generation failed"
    assert topic.inquiry_topic == "saved topic"
    recorded.assert_not_awaited()
    course_route_db.add.assert_not_called()


def _catalog(monkeypatch: pytest.MonkeyPatch, *, is_ta: bool) -> None:
    luna = SimpleNamespace(
        model_id="openai/gpt-6-luna",
        name="GPT-6 Luna",
        description="Fast.",
        provider_id="openai",
        input_price_usd=Decimal("0.1"),
        output_price_usd=Decimal("0.5"),
        sort_order=4,
    )
    monkeypatch.setattr(
        "app.crud.inquiry_model.list_inquiry_models", AsyncMock(return_value=[luna])
    )
    monkeypatch.setattr(
        course_crud, "is_active_ta_anywhere", AsyncMock(return_value=is_ta)
    )


def test_inquiry_models_need_auth(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/inquiry-models").status_code == 401


def test_student_who_is_not_a_ta_cannot_list_inquiry_models(
    auth_client: TestClient, store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_user(store, account_id="student1", role=UserRole.USER)
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account_id": "student1", "password": "password1"},
    )
    _catalog(monkeypatch, is_ta=False)

    response = auth_client.get(
        "/api/v1/inquiry-models", headers={"Authorization": bearer_from(login)}
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("role", "is_ta"), [(UserRole.TEACHER, False), (UserRole.USER, True)]
)
def test_teacher_or_ta_lists_inquiry_models_as_a_json_array(
    auth_client: TestClient,
    store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
    role: UserRole,
    is_ta: bool,
) -> None:
    seed_user(store, account_id="caller1", role=role)
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account_id": "caller1", "password": "password1"},
    )
    _catalog(monkeypatch, is_ta=is_ta)

    response = auth_client.get(
        "/api/v1/inquiry-models", headers={"Authorization": bearer_from(login)}
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "model_id": "openai/gpt-6-luna",
            "name": "GPT-6 Luna",
            "description": "Fast.",
            "provider_id": "openai",
            "input_price_usd": 0.1,
            "output_price_usd": 0.5,
        }
    ]
