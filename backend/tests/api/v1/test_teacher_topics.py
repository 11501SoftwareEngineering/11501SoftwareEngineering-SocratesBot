"""Teacher topic create / update / delete API tests (mocked CRUD)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, call
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.enums import UserRole
from app.crud import course as course_crud
from app.crud import topic as topic_crud
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def _login(
    client: TestClient,
    store: FakeStore,
    account: str = "teacher1",
    role: UserRole = UserRole.TEACHER,
) -> tuple[str, object]:
    user = seed_user(store, account_id=account, name="Teacher One", role=role)
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
        "title": "Old title",
        "description": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/teacher/topics"),
        ("put", f"/api/v1/teacher/topics/{uuid4()}"),
        ("delete", f"/api/v1/teacher/topics/{uuid4()}"),
    ],
)
def test_teacher_topics_require_auth(
    auth_client: TestClient, method: str, path: str
) -> None:
    response = auth_client.request(method, path, json={"title": "x"})
    assert response.status_code == 401


def test_student_cannot_create_topic(auth_client: TestClient, store: FakeStore) -> None:
    bearer, _ = _login(auth_client, store, account="student1", role=UserRole.USER)
    response = auth_client.post(
        "/api/v1/teacher/topics",
        headers={"Authorization": bearer},
        json={"course_id": str(uuid4()), "title": "T"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Teacher privileges required"


def test_create_topic_returns_topic_and_commits(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login(auth_client, store)
    course = SimpleNamespace(id=uuid4())
    created = _topic(course_id=course.id, title="T", description="D")
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    instructor_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(course_crud, "is_course_instructor", instructor_mock)
    create_mock = AsyncMock(return_value=created)
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)

    response = auth_client.post(
        "/api/v1/teacher/topics",
        headers={"Authorization": bearer},
        json={"course_id": str(course.id), "title": "T", "description": "D"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "topic_id": str(created.id),
        "course_id": str(course.id),
        "title": "T",
        "description": "D",
        "message": "Topic created",
    }
    instructor_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, teacher_id=teacher.id
    )
    assert create_mock.await_args == call(
        course_route_db,
        course_id=course.id,
        created_by=teacher.id,
        title="T",
        description="D",
    )
    course_route_db.commit.assert_awaited_once()


@pytest.mark.parametrize(
    "payload",
    [
        {"course_id": str(uuid4()), "title": ""},
        {"course_id": str(uuid4())},
        {"title": "T"},
    ],
)
def test_create_topic_missing_title_or_course_rejected(
    auth_client: TestClient, store: FakeStore, payload: dict
) -> None:
    bearer, _ = _login(auth_client, store)
    response = auth_client.post(
        "/api/v1/teacher/topics",
        headers={"Authorization": bearer},
        json=payload,
    )
    assert response.status_code == 422


def test_create_topic_missing_course_returns_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=None))
    create_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)

    response = auth_client.post(
        "/api/v1/teacher/topics",
        headers={"Authorization": bearer},
        json={"course_id": str(uuid4()), "title": "T"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"
    create_mock.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


def test_create_topic_non_instructor_forbidden(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=False)
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "create_topic", create_mock)

    response = auth_client.post(
        "/api/v1/teacher/topics",
        headers={"Authorization": bearer},
        json={"course_id": str(course.id), "title": "T"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Course instructor required"
    create_mock.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


def test_create_topic_db_error_rolls_back(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        topic_crud, "create_topic", AsyncMock(side_effect=RuntimeError("db down"))
    )

    with pytest.raises(RuntimeError):
        auth_client.post(
            "/api/v1/teacher/topics",
            headers={"Authorization": bearer},
            json={"course_id": str(course.id), "title": "T"},
        )
    course_route_db.rollback.assert_awaited_once()
    course_route_db.commit.assert_not_awaited()


def test_update_topic_returns_topic_and_commits(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login(auth_client, store)
    topic = _topic()
    updated = _topic(
        id=topic.id, course_id=topic.course_id, title="New", description="D2"
    )
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    instructor_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(course_crud, "is_course_instructor", instructor_mock)
    update_mock = AsyncMock(return_value=updated)
    monkeypatch.setattr(topic_crud, "update_topic", update_mock)

    response = auth_client.put(
        f"/api/v1/teacher/topics/{topic.id}",
        headers={"Authorization": bearer},
        json={"title": "New", "description": "D2"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "topic_id": str(topic.id),
        "course_id": str(topic.course_id),
        "title": "New",
        "description": "D2",
        "message": "Topic updated",
    }
    instructor_mock.assert_awaited_once_with(
        course_route_db, course_id=topic.course_id, teacher_id=teacher.id
    )
    assert update_mock.await_args == call(
        course_route_db, topic, title="New", description="D2"
    )
    course_route_db.commit.assert_awaited_once()


def test_update_topic_empty_title_rejected(
    auth_client: TestClient, store: FakeStore
) -> None:
    bearer, _ = _login(auth_client, store)
    response = auth_client.put(
        f"/api/v1/teacher/topics/{uuid4()}",
        headers={"Authorization": bearer},
        json={"title": ""},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("put", {"json": {"title": "T"}}),
        ("delete", {}),
    ],
)
def test_missing_topic_returns_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    kwargs: dict,
) -> None:
    bearer, _ = _login(auth_client, store)
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=None))
    instructor_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "is_course_instructor", instructor_mock)

    response = auth_client.request(
        method,
        f"/api/v1/teacher/topics/{uuid4()}",
        headers={"Authorization": bearer},
        **kwargs,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Topic not found"
    instructor_mock.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "kwargs", "write_fn"),
    [
        ("put", {"json": {"title": "T"}}, "update_topic"),
        ("delete", {}, "delete_topic"),
    ],
)
def test_non_instructor_cannot_modify_topic(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    kwargs: dict,
    write_fn: str,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic()
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=False)
    )
    write_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, write_fn, write_mock)

    response = auth_client.request(
        method,
        f"/api/v1/teacher/topics/{topic.id}",
        headers={"Authorization": bearer},
        **kwargs,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Course instructor required"
    write_mock.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


def test_delete_topic_returns_204_and_commits(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    topic = _topic()
    monkeypatch.setattr(topic_crud, "get_topic_by_id", AsyncMock(return_value=topic))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=True)
    )
    delete_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "delete_topic", delete_mock)

    response = auth_client.delete(
        f"/api/v1/teacher/topics/{topic.id}",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 204
    assert response.content == b""
    delete_mock.assert_awaited_once_with(course_route_db, topic)
    course_route_db.commit.assert_awaited_once()


def test_list_course_topics_requires_auth(auth_client: TestClient) -> None:
    response = auth_client.get(f"/api/v1/teacher/courses/{uuid4()}/topics")
    assert response.status_code == 401


def test_student_cannot_list_teacher_topics(
    auth_client: TestClient, store: FakeStore
) -> None:
    bearer, _ = _login(auth_client, store, account="student1", role=UserRole.USER)
    response = auth_client.get(
        f"/api/v1/teacher/courses/{uuid4()}/topics",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Teacher privileges required"


def test_list_course_topics_returns_course_and_counts(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login(auth_client, store)
    course = SimpleNamespace(id=uuid4(), name="SE", invitation_code="ABCD2345")
    first = _topic(course_id=course.id, title="T1", description="D1")
    second = _topic(course_id=course.id, title="T2")
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    instructor_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(course_crud, "is_course_instructor", instructor_mock)
    list_mock = AsyncMock(return_value=[(first, 3), (second, 0)])
    monkeypatch.setattr(topic_crud, "list_topics_with_completed_count", list_mock)

    response = auth_client.get(
        f"/api/v1/teacher/courses/{course.id}/topics",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "SE",
        "invite_code": "ABCD2345",
        "topics": [
            {
                "topic_id": str(first.id),
                "title": "T1",
                "description": "D1",
                "answered_count": 3,
            },
            {
                "topic_id": str(second.id),
                "title": "T2",
                "description": None,
                "answered_count": 0,
            },
        ],
    }
    instructor_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, teacher_id=teacher.id
    )
    list_mock.assert_awaited_once_with(course_route_db, course.id)
    course_route_db.commit.assert_not_awaited()


def test_list_course_topics_missing_course_returns_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=None))
    list_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "list_topics_with_completed_count", list_mock)

    response = auth_client.get(
        f"/api/v1/teacher/courses/{uuid4()}/topics",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"
    list_mock.assert_not_awaited()


def test_list_course_topics_non_instructor_forbidden(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store)
    course = SimpleNamespace(id=uuid4(), name="SE", invitation_code="ABCD2345")
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=False)
    )
    list_mock = AsyncMock()
    monkeypatch.setattr(topic_crud, "list_topics_with_completed_count", list_mock)

    response = auth_client.get(
        f"/api/v1/teacher/courses/{course.id}/topics",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Course instructor required"
    list_mock.assert_not_awaited()
