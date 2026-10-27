"""Student course topic list / topic explanation API tests (mocked CRUD)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.enums import SessionStatus, UserRole
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import topic as topic_crud
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def _login(
    client: TestClient,
    store: FakeStore,
    account: str = "student1",
    role: UserRole = UserRole.USER,
) -> tuple[str, object]:
    user = seed_user(store, account_id=account, role=role)
    login = client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": "password1"},
    )
    assert login.status_code == 200
    return bearer_from(login), user


def _topic(**overrides) -> SimpleNamespace:
    values = {
        "id": uuid4(),
        "course_id": uuid4(),
        "title": "T",
        "description": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/student/courses/{uuid4()}/topics",
        f"/api/v1/student/topics/{uuid4()}/explanation",
    ],
)
def test_student_topics_require_auth(auth_client: TestClient, path: str) -> None:
    assert auth_client.get(path).status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/student/courses/{uuid4()}/topics",
        f"/api/v1/student/topics/{uuid4()}/explanation",
    ],
)
def test_teacher_cannot_use_student_topics(
    auth_client: TestClient, store: FakeStore, path: str
) -> None:
    bearer, _ = _login(auth_client, store, account="teacher1", role=UserRole.TEACHER)
    response = auth_client.get(path, headers={"Authorization": bearer})
    assert response.status_code == 403
    assert response.json()["detail"] == "Student privileges required"


def test_list_course_topics_returns_session_state(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, student = _login(auth_client, store)
    course = SimpleNamespace(id=uuid4(), name="SE", invitation_code="ABCD2345")
    started = _topic(course_id=course.id, title="T1", description="D1")
    not_started = _topic(course_id=course.id, title="T2")
    session_id = uuid4()
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    member_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(session_crud, "is_course_member", member_mock)
    list_mock = AsyncMock(
        return_value=[
            (started, SessionStatus.COMPLETED.value, session_id),
            (not_started, None, None),
        ]
    )
    monkeypatch.setattr(topic_crud, "list_topics_with_user_session", list_mock)

    response = auth_client.get(
        f"/api/v1/student/courses/{course.id}/topics",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "SE",
        "invite_code": "ABCD2345",
        "topics": [
            {
                "topic_id": str(started.id),
                "title": "T1",
                "description": "D1",
                "status": "COMPLETED",
                "session_id": str(session_id),
            },
            {
                "topic_id": str(not_started.id),
                "title": "T2",
                "description": None,
                "status": None,
                "session_id": None,
            },
        ],
    }
    member_mock.assert_awaited_once_with(
        course_route_db, user_id=student.id, course_id=course.id
    )
    list_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, user_id=student.id
    )


def test_list_course_topics_missing_course_returns_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=None))
    list_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "list_topics_with_user_session", list_mock)

    response = auth_client.get(
        f"/api/v1/student/courses/{uuid4()}/topics",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"
    list_mock.assert_not_awaited()


def test_list_course_topics_non_member_forbidden(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = SimpleNamespace(id=uuid4(), name="SE", invitation_code="ABCD2345")
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(session_crud, "is_course_member", AsyncMock(return_value=False))
    list_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "list_topics_with_user_session", list_mock)

    response = auth_client.get(
        f"/api/v1/student/courses/{course.id}/topics",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Course membership required"
    list_mock.assert_not_awaited()


def test_topic_explanation_returns_title_background_and_key_terms(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, student = _login(auth_client, store)
    topic = _topic(title="T1", description="D1")
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    member_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(session_crud, "is_course_member", member_mock)

    response = auth_client.get(
        f"/api/v1/student/topics/{topic.id}/explanation",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 200
    assert response.json() == {
        "topic_id": str(topic.id),
        "title": "T1",
        "background": "D1",
        "key_terms": [],
    }
    member_mock.assert_awaited_once_with(
        course_route_db, user_id=student.id, course_id=topic.course_id
    )


def test_topic_explanation_missing_topic_returns_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=None))
    member_mock = AsyncMock()
    monkeypatch.setattr(session_crud, "is_course_member", member_mock)

    response = auth_client.get(
        f"/api/v1/student/topics/{uuid4()}/explanation",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Topic not found"
    member_mock.assert_not_awaited()


def test_topic_explanation_non_member_forbidden(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic()
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    monkeypatch.setattr(session_crud, "is_course_member", AsyncMock(return_value=False))

    response = auth_client.get(
        f"/api/v1/student/topics/{topic.id}/explanation",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Course membership required"
