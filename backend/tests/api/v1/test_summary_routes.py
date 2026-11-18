"""Class-summary API tests. Model preparation is never started."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.enums import UserRole
from app.crud import course as course_crud
from app.crud import report as report_crud
from app.crud import session as session_crud
from app.crud import summary as summary_crud
from app.models.session import Session
from app.models.topic import Topic
from app.services import summary_runner
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
        self.summary_attempts: list[SimpleNamespace] = []
        self.draft: SimpleNamespace | None = None
        self.summaries_scheduled: list = []
        self.instructor_id = None
        self.member_ids: set = set()

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

    async def is_instructor(_db, *, course_id, teacher_id):
        return (
            course_id == memory.topic.course_id and teacher_id == memory.instructor_id
        )

    async def is_member(_db, *, user_id, course_id):
        return course_id == memory.topic.course_id and user_id in memory.member_ids

    async def ready_bodies(_db, topic_id):
        assert topic_id == memory.topic.id
        ready = [
            row
            for row in memory.attempts
            if row.status == "ready" and row.result_json is not None
        ]
        return [] if not ready else [(str(ready[-1].id), ready[-1].result_json)]

    async def latest_attempt(_db, topic_id):
        rows = [row for row in memory.summary_attempts if row.topic_id == topic_id]
        return rows[-1] if rows else None

    async def insert_attempt(_db, *, topic_id, request_json):
        row = SimpleNamespace(
            id=uuid4(), topic_id=topic_id, status="pending", request_json=request_json
        )
        memory.summary_attempts.append(row)
        return row

    async def latest_summary(_db, topic_id):
        if memory.draft is None or memory.draft.topic_id != topic_id:
            return None
        return memory.draft

    async def published_document(_db, topic_id):
        if memory.draft is None or memory.draft.topic_id != topic_id:
            return None
        return memory.draft.body.get("published")

    async def published_version(_db, topic_id):
        if memory.draft is None or memory.draft.topic_id != topic_id:
            return None
        return memory.draft.body.get("published_version")

    async def topic_dialogues(_db, topic_id):
        assert topic_id == memory.topic.id
        return [(memory.session, "Ada")]

    monkeypatch.setattr(course_crud, "is_course_instructor", is_instructor)
    monkeypatch.setattr(session_crud, "is_course_member", is_member)
    monkeypatch.setattr(report_crud, "topic_dialogues", topic_dialogues)
    monkeypatch.setattr(summary_crud, "ready_report_bodies", ready_bodies)
    monkeypatch.setattr(summary_crud, "latest_attempt", latest_attempt)
    monkeypatch.setattr(summary_crud, "insert_attempt", insert_attempt)
    monkeypatch.setattr(summary_crud, "latest_summary", latest_summary)
    monkeypatch.setattr(summary_crud, "published_document", published_document)
    monkeypatch.setattr(summary_crud, "published_version", published_version)
    monkeypatch.setattr(
        summary_runner,
        "schedule",
        lambda attempt_id: memory.summaries_scheduled.append(attempt_id),
    )


def test_summary_publish_stays_stable_until_withdraw(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    teacher_bearer, teacher = _login(auth_client, store, "teacher1", UserRole.TEACHER)
    student_bearer, student = _login(auth_client, store, "student1", UserRole.USER)
    outsider_bearer, _outsider = _login(
        auth_client, store, "outsider", UserRole.TEACHER
    )
    memory = _Memory()
    memory.instructor_id = teacher.id
    memory.member_ids.add(student.id)
    memory.session.user_id = student.id
    memory.add_attempt("ready", dict(READY))
    memory.draft = SimpleNamespace(
        id=uuid4(),
        topic_id=memory.topic.id,
        version=1,
        body={
            "status": "reviewed",
            "overview": "The class compared two accounts.",
            "viewpoint_summary": "Most revised the first claim.",
            "denominator": 2,
            "groups": [
                {
                    "name": "revised",
                    "conditions": "changed the claim",
                    "count": 1,
                    "percentage": 50,
                    "report_ids": ["report-1"],
                }
            ],
            "ungrouped_report_ids": ["report-2"],
            "published": None,
            "published_version": None,
        },
    )
    _install(monkeypatch, course_route_db, memory)

    started = auth_client.post(
        f"/api/v1/topics/{memory.topic.id}/summary",
        headers={"Authorization": teacher_bearer},
    )
    memory.draft.body["overview"] = "Ada changed her claim."
    named = auth_client.post(
        f"/api/v1/topics/{memory.topic.id}/summary/publish",
        headers={"Authorization": teacher_bearer},
        json={"version": 1},
    )
    memory.draft.body["overview"] = "The class compared two accounts."
    published = auth_client.post(
        f"/api/v1/topics/{memory.topic.id}/summary/publish",
        headers={"Authorization": teacher_bearer},
        json={"version": 1},
    )
    student_read = auth_client.get(
        f"/api/v1/topics/{memory.topic.id}/summary/published",
        headers={"Authorization": student_bearer},
    )
    edited = auth_client.patch(
        f"/api/v1/topics/{memory.topic.id}/summary",
        headers={"Authorization": teacher_bearer},
        json={
            "version": 1,
            "overview": "A later draft.",
            "viewpoint_summary": "Still the published claim.",
        },
    )
    student_again = auth_client.get(
        f"/api/v1/topics/{memory.topic.id}/summary/published",
        headers={"Authorization": student_bearer},
    )
    denied = auth_client.post(
        f"/api/v1/topics/{memory.topic.id}/summary/withdraw",
        headers={"Authorization": outsider_bearer},
    )
    withdrawn = auth_client.post(
        f"/api/v1/topics/{memory.topic.id}/summary/withdraw",
        headers={"Authorization": teacher_bearer},
    )
    after_withdraw = auth_client.get(
        f"/api/v1/topics/{memory.topic.id}/summary/published",
        headers={"Authorization": student_bearer},
    )

    assert started.status_code == 200
    assert started.json()["topic_status"] == "conversation"
    assert started.json()["preparation_status"] == "pending"
    assert memory.topic.stage == "conversation"
    assert memory.summaries_scheduled
    assert named.status_code == 400
    assert published.status_code == 200
    assert "report_ids" not in student_read.text
    assert "Ada" not in student_read.text
    assert (
        student_read.json()["summary"]["overview"] == "The class compared two accounts."
    )
    assert edited.status_code == 200
    assert edited.json()["summary"]["summary_status"] == "draft"
    assert (
        student_again.json()["summary"]["overview"]
        == "The class compared two accounts."
    )
    assert denied.status_code == 403
    assert withdrawn.status_code == 200
    assert after_withdraw.json()["summary"] is None


def test_privacy_and_result_routes_are_gone(auth_client: TestClient) -> None:
    session_id = uuid4()
    privacy = auth_client.patch(
        f"/api/v1/student/sessions/{session_id}/privacy",
        json={"is_anonymous": True},
    )
    result = auth_client.get(f"/api/v1/student/sessions/{session_id}/result")

    assert privacy.status_code == 404
    assert result.status_code == 404
