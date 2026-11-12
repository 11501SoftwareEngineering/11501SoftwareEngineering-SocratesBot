"""Inquiry setup API tests. Generation uses a stub and never calls OpenAI."""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.enums import UserRole
from app.crud import attempt as attempt_crud
from app.crud import course as course_crud
from app.services import inquiry_runner
from app.services.model_client import ModelCallError
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


class _Attempts:
    def __init__(self) -> None:
        self.rows: dict = {}

    def latest(self, topic_id):
        rows = [row for row in self.rows.values() if row.topic_id == topic_id]
        if not rows:
            return None
        return max(rows, key=lambda row: row.created_at)


def _install_attempts(monkeypatch: pytest.MonkeyPatch) -> _Attempts:
    memory = _Attempts()

    async def create_inquiry_attempt(_db, *, topic_id, request_json):
        row = SimpleNamespace(
            id=uuid4(),
            topic_id=topic_id,
            kind="inquiry_fields",
            status="pending",
            request_json=request_json,
            result_json=None,
            lease_expires_at=None,
            created_at=datetime.now(UTC),
        )
        memory.rows[row.id] = row
        return row

    async def get_attempt(_db, attempt_id):
        return memory.rows.get(attempt_id)

    async def latest_inquiry_attempt(_db, topic_id):
        return memory.latest(topic_id)

    async def mark_processing(_db, attempt_id):
        row = memory.rows[attempt_id]
        if row.status == "pending":
            row.status = "processing"

    async def refresh_lease(_db, attempt_id, *, seconds):
        row = memory.rows[attempt_id]
        if row.status == "processing":
            row.lease_expires_at = datetime.now(UTC)

    async def mark_ready_if_processing(_db, attempt_id, result_json):
        row = memory.rows[attempt_id]
        if row.status != "processing":
            return False
        row.status = "ready"
        row.result_json = result_json
        return True

    async def mark_failed_if_processing(_db, attempt_id):
        row = memory.rows[attempt_id]
        if row.status != "processing":
            return False
        row.status = "failed"
        row.result_json = None
        return True

    monkeypatch.setattr(attempt_crud, "create_inquiry_attempt", create_inquiry_attempt)
    monkeypatch.setattr(attempt_crud, "get_attempt", get_attempt)
    monkeypatch.setattr(attempt_crud, "latest_inquiry_attempt", latest_inquiry_attempt)
    monkeypatch.setattr(attempt_crud, "mark_processing", mark_processing)
    monkeypatch.setattr(attempt_crud, "refresh_lease", refresh_lease)
    monkeypatch.setattr(
        attempt_crud, "mark_ready_if_processing", mark_ready_if_processing
    )
    monkeypatch.setattr(
        attempt_crud, "mark_failed_if_processing", mark_failed_if_processing
    )
    return memory


@asynccontextmanager
async def _scope():
    yield SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock(), flush=AsyncMock())


class _Gate:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.result = result
        self.error = error
        self.calls = 0

    async def complete_json(self, *, instructions: str, material: str) -> dict:
        self.calls += 1
        self.started.set()
        await asyncio.to_thread(self.release.wait)
        if self.error is not None:
            raise self.error
        return self.result


def _ready(monkeypatch: pytest.MonkeyPatch, topic, *, instructor_id=None) -> None:
    monkeypatch.setattr("app.crud.topic.get_topic_by_id", AsyncMock(return_value=topic))

    async def is_instructor(_db, *, course_id, teacher_id):
        assert course_id == topic.course_id
        if instructor_id is None:
            return True
        return teacher_id == instructor_id

    monkeypatch.setattr(course_crud, "is_course_instructor", is_instructor)
    monkeypatch.setattr(inquiry_runner, "session_scope", _scope)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", type(settings.OPENAI_API_KEY)(KEY))


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
        json={"expected_version": 1},
    )
    assert missing_topic.status_code == 409
    assert missing_topic.json()["detail"] == "Incomplete setup: topic"
    assert topic.stage == "setup"

    topic.inquiry_topic = "Cities"
    topic.age_band = None
    bad_age = auth_client.post(
        f"/api/v1/topics/{topic.id}/publish",
        headers={"Authorization": bearer},
        json={"expected_version": 1},
    )
    assert bad_age.status_code == 409
    assert bad_age.json()["detail"] == "Incomplete setup: age_band"
    rejected = auth_client.put(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
        json={
            "expected_version": 1,
            "setup": {"age_band": "18+", "topic": "Cities", "core_question": "Why?"},
        },
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
        json={"expected_version": 1},
    )
    assert illegal_age.status_code == 409
    assert illegal_age.json()["detail"] == "Incomplete setup: age_band"
    assert topic.stage == "setup"
    course_route_db.commit.assert_not_awaited()


def test_save_persists_fields_and_leaves_attempt_unsaved(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic()
    memory = _install_attempts(monkeypatch)
    _ready(monkeypatch, topic)
    attempt = SimpleNamespace(
        id=uuid4(),
        topic_id=topic.id,
        status="ready",
        result_json=GENERATED,
        lease_expires_at=None,
        created_at=datetime.now(UTC),
    )
    memory.rows[attempt.id] = attempt

    response = auth_client.put(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
        json={
            "expected_version": 1,
            "content_language": "zh-TW",
            "setup": {
                "age_band": "university_plus",
                "max_turns": 5,
                "topic": "Cities",
                "core_question": "Who maintains them?",
                "inquiry_focus": "the public cost",
                "opening_message": "",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["setup"]["topic"] == "Cities"
    assert "opening_message" not in body["setup"]
    assert topic.opening_message is None
    assert body["content_language"] == "zh-TW"
    assert body["attempt"]["body"]["topic"] == "generated topic"
    assert topic.inquiry_topic == "Cities"
    assert topic.exclusions == "unspecified"
    assert topic.version == 2
    assert topic.stage == "setup"
    course_route_db.commit.assert_awaited()


def test_generation_returns_before_ready_and_later_read_is_instructor_only(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bearer, teacher = _login(auth_client, store)
    outsider_bearer, _ = _login(auth_client, store, account="outsider")
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    memory = _install_attempts(monkeypatch)
    gate = _Gate(result=GENERATED)
    _ready(monkeypatch, topic, instructor_id=teacher.id)
    monkeypatch.setattr(inquiry_runner, "client", gate)
    caplog.set_level(logging.INFO)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/generate",
        headers={"Authorization": bearer},
        json={
            "age_band": "13-15",
            "max_turns": 10,
            "content_language": "zh-TW",
            "course_description": DIALOGUE,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert "body" not in response.json()
    assert KEY not in response.text
    course_route_db.commit.assert_awaited()
    attempt_id = UUID(response.json()["attempt_id"])
    assert gate.started.wait(5)
    try:
        waiting = auth_client.get(
            f"/api/v1/topics/{topic.id}/setup",
            headers={"Authorization": bearer},
        )
        assert waiting.status_code == 200
        attempt = waiting.json()["attempt"]
        assert attempt["status"] == "processing"
        assert "body" not in attempt
        assert waiting.json()["setup"]["topic"] == "saved topic"
        assert memory.rows[attempt_id].status == "processing"
    finally:
        gate.release.set()
        inquiry_runner.join(attempt_id)

    ready = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
    )
    assert ready.status_code == 200
    assert ready.json()["attempt"]["status"] == "ready"
    assert ready.json()["attempt"]["body"]["topic"] == "generated topic"
    assert ready.json()["setup"]["topic"] == "saved topic"
    assert topic.inquiry_topic == "saved topic"
    denied = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": outsider_bearer},
    )
    assert denied.status_code == 403
    stored = memory.rows[attempt_id]
    assert KEY not in f"{stored.request_json} {stored.result_json} {caplog.text}"
    assert DIALOGUE not in caplog.text


def test_failed_regeneration_keeps_the_saved_inquiry(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic(inquiry_topic="saved topic", core_question="saved question")
    memory = _install_attempts(monkeypatch)
    gate = _Gate(error=ModelCallError(503))
    _ready(monkeypatch, topic)
    monkeypatch.setattr(inquiry_runner, "client", gate)
    caplog.set_level(logging.INFO)

    response = auth_client.post(
        f"/api/v1/topics/{topic.id}/setup/refine",
        headers={"Authorization": bearer},
        json={
            "setup": {"topic": "saved topic", "core_question": "saved question"},
            "feedback": DIALOGUE,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    course_route_db.commit.assert_awaited()
    attempt_id = UUID(response.json()["attempt_id"])
    try:
        assert gate.started.wait(5)
    finally:
        gate.release.set()
        inquiry_runner.join(attempt_id)

    failed = auth_client.get(
        f"/api/v1/topics/{topic.id}/setup",
        headers={"Authorization": bearer},
    )
    assert failed.status_code == 200
    assert failed.json()["attempt"]["status"] == "failed"
    assert "body" not in failed.json()["attempt"]
    assert failed.json()["setup"]["topic"] == "saved topic"
    assert topic.inquiry_topic == "saved topic"
    assert memory.rows[attempt_id].result_json is None
    assert KEY not in caplog.text
    assert DIALOGUE not in caplog.text
