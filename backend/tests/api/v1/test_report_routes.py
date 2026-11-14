"""Personal and teaching report API tests. Model preparation is never started."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.enums import UserRole
from app.crud import course as course_crud
from app.crud import report as report_crud
from app.models.session import Session
from app.models.topic import Topic
from app.services import report_runner
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user

READY = {
    "viewpoint_summary": "kept the earlier claim",
    "final_viewpoint": "the second account is narrower",
    "viewpoint_status": "revised",
    "evidence_status": "partial",
}


def _login(client: TestClient, store: FakeStore, account: str, role: UserRole):
    user = seed_user(store, account_id=account, role=role, name="Ada")
    response = client.post(
        "/api/v1/auth/login",
        json={"account_id": account, "password": "password1"},
    )
    assert response.status_code == 200
    return bearer_from(response), user


class _Memory:
    def __init__(self) -> None:
        self.topic = SimpleNamespace(
            id=uuid4(), course_id=uuid4(), stage="conversation"
        )
        self.session = SimpleNamespace(
            id=uuid4(),
            user_id=None,
            topic_id=self.topic.id,
            outcome="completed",
        )
        self.attempts: list[SimpleNamespace] = []
        self.reports_scheduled: list = []
        self.instructor_id = None

    def add_attempt(self, status: str, body: dict | None) -> SimpleNamespace:
        row = SimpleNamespace(
            id=uuid4(),
            session_id=self.session.id,
            status=status,
            result_json=body,
        )
        self.attempts.append(row)
        return row


def _install(monkeypatch: pytest.MonkeyPatch, db: AsyncMock, memory: _Memory) -> None:
    async def get(model, ident):
        if model is Topic and ident == memory.topic.id:
            return memory.topic
        if model is Session and ident == memory.session.id:
            return memory.session
        return None

    db.get.side_effect = get

    async def owned(_db, *, session_id, user_id):
        if session_id != memory.session.id or user_id != memory.session.user_id:
            return None
        return memory.session

    async def list_for_session(_db, session_id):
        return [row for row in memory.attempts if row.session_id == session_id]

    async def list_for_sessions(_db, session_ids):
        return [row for row in memory.attempts if row.session_id in session_ids]

    async def insert_pending(_db, session_id):
        return memory.add_attempt("pending", None)

    async def is_instructor(_db, *, course_id, teacher_id):
        return (
            course_id == memory.topic.course_id and teacher_id == memory.instructor_id
        )

    async def topic_dialogues(_db, topic_id):
        assert topic_id == memory.topic.id
        return [(memory.session, "Ada")]

    monkeypatch.setattr(report_crud, "owned_session", owned)
    monkeypatch.setattr(report_crud, "list_for_session", list_for_session)
    monkeypatch.setattr(report_crud, "list_for_sessions", list_for_sessions)
    monkeypatch.setattr(report_crud, "insert_pending", insert_pending)
    monkeypatch.setattr(report_crud, "student_turn_count", AsyncMock(return_value=2))
    monkeypatch.setattr(report_crud, "topic_dialogues", topic_dialogues)
    monkeypatch.setattr(report_crud, "class_size", AsyncMock(return_value=4))
    monkeypatch.setattr(course_crud, "is_course_instructor", is_instructor)
    monkeypatch.setattr(
        report_runner,
        "schedule",
        lambda attempt_id: memory.reports_scheduled.append(attempt_id),
    )


def test_student_read_hides_the_name_and_teaching_read_shows_it(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student_bearer, student = _login(auth_client, store, "student1", UserRole.USER)
    teacher_bearer, teacher = _login(auth_client, store, "teacher1", UserRole.TEACHER)
    memory = _Memory()
    memory.session.user_id = student.id
    memory.instructor_id = teacher.id
    memory.add_attempt("ready", dict(READY))
    _install(monkeypatch, course_route_db, memory)

    student_read = auth_client.get(
        f"/api/v1/sessions/{memory.session.id}/report",
        headers={"Authorization": student_bearer},
    )
    teaching_read = auth_client.get(
        f"/api/v1/topics/{memory.topic.id}/reports",
        headers={"Authorization": teacher_bearer},
    )

    assert student_read.status_code == 200
    assert "student_display_name" not in student_read.text
    assert (
        student_read.json()["report"]["viewpoint_summary"] == READY["viewpoint_summary"]
    )
    assert teaching_read.status_code == 200
    assert teaching_read.json()["reports"][0]["student_display_name"] == "Ada"
    assert teaching_read.json()["ready_count"] == 1


def test_uncompleted_dialogue_and_classmate_have_no_report(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_bearer, owner = _login(auth_client, store, "owner", UserRole.USER)
    classmate_bearer, _ = _login(auth_client, store, "classmate", UserRole.USER)
    memory = _Memory()
    memory.session.user_id = owner.id
    memory.session.outcome = "open"
    _install(monkeypatch, course_route_db, memory)

    rejected = auth_client.post(
        f"/api/v1/sessions/{memory.session.id}/report",
        headers={"Authorization": owner_bearer},
    )
    missing = auth_client.get(
        f"/api/v1/sessions/{memory.session.id}/report",
        headers={"Authorization": classmate_bearer},
    )

    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "Dialogue is not completed"
    assert missing.status_code == 404
    assert memory.reports_scheduled == []


def test_failed_retry_keeps_the_ready_body(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, student = _login(auth_client, store, "student1", UserRole.USER)
    memory = _Memory()
    memory.session.user_id = student.id
    ready = memory.add_attempt("ready", dict(READY))
    memory.add_attempt("failed", None)
    _install(monkeypatch, course_route_db, memory)

    started = auth_client.post(
        f"/api/v1/sessions/{memory.session.id}/report",
        headers={"Authorization": bearer},
    )
    reread = auth_client.get(
        f"/api/v1/sessions/{memory.session.id}/report",
        headers={"Authorization": bearer},
    )

    assert started.status_code == 200
    assert started.json()["report_status"] == "pending"
    assert started.json()["report"]["viewpoint_summary"] == READY["viewpoint_summary"]
    assert memory.reports_scheduled
    assert memory.attempts[0].id == ready.id
    assert memory.attempts[0].status == "ready"
    assert reread.json()["report"]["report_id"] == str(ready.id)
    assert memory.session.outcome == "completed"
