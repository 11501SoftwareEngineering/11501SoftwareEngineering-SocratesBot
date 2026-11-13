"""Topic API tests: list / create / delete / explanation (mocked CRUD)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.enums import UserRole
from app.crud import course as course_crud
from app.crud import session as session_crud
from app.crud import topic as topic_crud
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def _login(
    client: TestClient,
    store: FakeStore,
    account: str = "user1",
    role: UserRole = UserRole.USER,
) -> tuple[str, object]:
    user = seed_user(store, account_id=account, role=role)
    login = client.post(
        "/api/v1/auth/login",
        json={"account_id": account, "password": "password1"},
    )
    assert login.status_code == 200
    return bearer_from(login), user


def _course(**overrides):
    base = {"id": uuid4(), "name": "SE", "invitation_code": "ABCD2345"}
    base.update(overrides)
    return SimpleNamespace(**base)


def _topic(course_id, **overrides):
    base = {
        "id": uuid4(),
        "course_id": course_id,
        "title": "T1",
        "description": "Background",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_role(monkeypatch, db_role: str | None, course=None):
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=db_role))
    monkeypatch.setattr(
        course_crud,
        "is_course_instructor",
        AsyncMock(return_value=db_role == "TEACHER"),
    )


def test_student_topic_list_has_session_fields(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store)
    course = _course()
    _patch_role(monkeypatch, "STUDENT", course)
    started = _topic(course.id, title="Started")
    fresh = _topic(course.id, title="Fresh", description=None)
    session_id = uuid4()
    list_mock = AsyncMock(
        return_value=[
            (started, "IN_PROGRESS", session_id),
            (fresh, None, None),
        ]
    )
    monkeypatch.setattr(topic_crud, "list_topics_with_user_session", list_mock)

    response = auth_client.get(
        f"/api/v1/courses/{course.id}/topics", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "SE",
        "invite_code": "ABCD2345",
        "topics": [
            {
                "topic_id": str(started.id),
                "title": "Started",
                "description": "Background",
                "status": "IN_PROGRESS",
                "session_id": str(session_id),
            },
            {
                "topic_id": str(fresh.id),
                "title": "Fresh",
                "description": None,
                "status": None,
                "session_id": None,
            },
        ],
    }
    list_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, user_id=user.id
    )


@pytest.mark.parametrize("db_role", ["TEACHER", "TA"])
def test_staff_topic_list_has_answered_count(
    db_role: str,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    _patch_role(monkeypatch, db_role, course)
    topic = _topic(course.id)
    monkeypatch.setattr(
        topic_crud,
        "list_topics_with_completed_count",
        AsyncMock(return_value=[(topic, 3)]),
    )

    response = auth_client.get(
        f"/api/v1/courses/{course.id}/topics", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "SE",
        "invite_code": "ABCD2345",
        "topics": [
            {
                "topic_id": str(topic.id),
                "title": "T1",
                "description": "Background",
                "answered_count": 3,
            }
        ],
    }


@pytest.mark.parametrize(("exists", "expected"), [(True, 403), (False, 404)])
def test_topic_list_non_member_or_missing(
    exists: bool,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    _patch_role(monkeypatch, None, _course() if exists else None)
    response = auth_client.get(
        f"/api/v1/courses/{uuid4()}/topics", headers={"Authorization": bearer}
    )
    assert response.status_code == expected


def test_create_topic_in_path_course(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    _patch_role(monkeypatch, "TEACHER", course)
    topic = _topic(course.id, title="New")
    create_mock = AsyncMock(return_value=topic)
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)

    response = auth_client.post(
        f"/api/v1/courses/{course.id}/topics",
        headers={"Authorization": bearer},
        json={"title": "New", "description": "Background"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "topic_id": str(topic.id),
        "course_id": str(course.id),
        "title": "New",
        "description": "Background",
        "message": "Topic created",
    }
    create_mock.assert_awaited_once_with(
        course_route_db,
        course_id=course.id,
        created_by=user.id,
        title="New",
        description="Background",
    )
    course_route_db.commit.assert_awaited_once()


@pytest.mark.parametrize(
    ("db_role", "exists", "body", "expected"),
    [
        ("STUDENT", True, {"title": "x"}, 403),
        (None, True, {"title": "x"}, 403),
        ("TEACHER", False, {"title": "x"}, 404),
        ("TEACHER", True, {"title": ""}, 422),
    ],
)
def test_create_topic_errors(
    db_role: str | None,
    exists: bool,
    body: dict,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    _patch_role(monkeypatch, db_role, _course() if exists else None)
    create_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)
    response = auth_client.post(
        f"/api/v1/courses/{uuid4()}/topics",
        headers={"Authorization": bearer},
        json=body,
    )
    assert response.status_code == expected
    create_mock.assert_not_awaited()


def test_update_topic_endpoint_is_removed(
    auth_client: TestClient, store: FakeStore
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    response = auth_client.put(
        f"/api/v1/topics/{uuid4()}",
        headers={"Authorization": bearer},
        json={"title": "x"},
    )
    assert response.status_code == 405


def test_delete_topic_by_teacher(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    topic = _topic(course.id)
    _patch_role(monkeypatch, "TEACHER", course)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    delete_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "delete_topic", delete_mock)

    response = auth_client.delete(
        f"/api/v1/topics/{topic.id}", headers={"Authorization": bearer}
    )

    assert response.status_code == 204
    delete_mock.assert_awaited_once_with(course_route_db, topic)
    course_route_db.commit.assert_awaited_once()


def test_delete_topic_by_non_teacher_is_403(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = _course()
    _patch_role(monkeypatch, "STUDENT", course)
    monkeypatch.setattr(
        topic_crud, "get_topic_by_id", AsyncMock(return_value=_topic(course.id))
    )
    delete_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "delete_topic", delete_mock)
    response = auth_client.delete(
        f"/api/v1/topics/{uuid4()}", headers={"Authorization": bearer}
    )
    assert response.status_code == 403
    delete_mock.assert_not_awaited()


def test_delete_missing_topic_is_idempotent(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=None))
    response = auth_client.delete(
        f"/api/v1/topics/{uuid4()}", headers={"Authorization": bearer}
    )
    assert response.status_code == 204
    course_route_db.commit.assert_not_awaited()


def test_explanation_for_course_member(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = _course()
    topic = _topic(course.id)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    monkeypatch.setattr(session_crud, "is_course_member", AsyncMock(return_value=True))

    response = auth_client.get(
        f"/api/v1/topics/{topic.id}/explanation", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    assert response.json() == {
        "topic_id": str(topic.id),
        "title": "T1",
        "background": "Background",
        "key_terms": [],
    }


@pytest.mark.parametrize(("topic_exists", "expected"), [(True, 403), (False, 404)])
def test_explanation_non_member_or_missing(
    topic_exists: bool,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = _course()
    monkeypatch.setattr(
        topic_crud,
        "get_topic_by_id",
        AsyncMock(return_value=_topic(course.id) if topic_exists else None),
    )
    monkeypatch.setattr(session_crud, "is_course_member", AsyncMock(return_value=False))
    response = auth_client.get(
        f"/api/v1/topics/{uuid4()}/explanation", headers={"Authorization": bearer}
    )
    assert response.status_code == expected
