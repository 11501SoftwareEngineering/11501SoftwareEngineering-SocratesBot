"""Teacher course create / list / delete API tests (mocked CRUD)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, call
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.enums import UserRole
from app.crud import course as course_crud
from app.services.course_invites import INVITE_COLLISION_RETRIES
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def _login_teacher(
    client: TestClient, store: FakeStore, account: str = "teacher1"
) -> tuple[str, object]:
    teacher = seed_user(
        store,
        account_id=account,
        name="Teacher One",
        role=UserRole.TEACHER,
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": "password1"},
    )
    assert login.status_code == 200
    return bearer_from(login), teacher


def test_teacher_courses_require_auth(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/teacher/courses").status_code == 401


def test_non_teacher_forbidden(auth_client: TestClient, store: FakeStore) -> None:
    student = seed_user(store, account_id="student1")
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": student.account_id, "password": "password1"},
    )
    assert login.status_code == 200
    response = auth_client.get(
        "/api/v1/teacher/courses",
        headers={"Authorization": bearer_from(login)},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Teacher privileges required"


def test_create_course_seeds_instructor_and_returns_invite(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login_teacher(auth_client, store)
    course_id = uuid4()
    created = SimpleNamespace(
        id=course_id,
        name="SE",
        description="Fall",
        invitation_code="ABCD2345",
        created_by=teacher.id,
    )
    create_mock = AsyncMock(return_value=created)
    monkeypatch.setattr(
        "app.services.courses.generate_invite_code",
        lambda: "ABCD2345",
    )
    monkeypatch.setattr(course_crud, "create_course_with_instructor", create_mock)

    response = auth_client.post(
        "/api/v1/teacher/courses",
        headers={"Authorization": bearer},
        json={"name": "SE", "description": "Fall"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "course_id": str(course_id),
        "name": "SE",
        "description": "Fall",
        "invite_code": "ABCD2345",
        "message": "Course created",
    }
    create_mock.assert_awaited_once()
    kwargs = create_mock.await_args.kwargs
    assert kwargs["name"] == "SE"
    assert kwargs["description"] == "Fall"
    assert kwargs["created_by"] == teacher.id
    assert kwargs["invitation_code"] == "ABCD2345"
    course_route_db.commit.assert_awaited_once()


def _invite_unique_integrity_error() -> IntegrityError:
    orig = Exception("duplicate key value violates unique constraint")
    orig.constraint_name = "uq_courses_invitation_code"  # type: ignore[attr-defined]
    return IntegrityError("INSERT", {}, orig)


def test_create_course_retries_on_invite_unique_collision(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login_teacher(auth_client, store, account="teacher-retry")
    course_id = uuid4()
    created = SimpleNamespace(
        id=course_id,
        name="SE",
        description=None,
        invitation_code="SECOND01",
        created_by=teacher.id,
    )
    create_mock = AsyncMock(side_effect=[_invite_unique_integrity_error(), created])
    codes = iter(["FIRST001", "SECOND01"])
    monkeypatch.setattr(
        "app.services.courses.generate_invite_code",
        lambda: next(codes),
    )
    monkeypatch.setattr(course_crud, "create_course_with_instructor", create_mock)

    response = auth_client.post(
        "/api/v1/teacher/courses",
        headers={"Authorization": bearer},
        json={"name": "SE"},
    )
    assert response.status_code == 200
    assert response.json()["invite_code"] == "SECOND01"
    assert create_mock.await_count == 2
    course_route_db.rollback.assert_awaited()
    course_route_db.commit.assert_awaited_once()


def test_create_course_other_integrity_error_is_not_retried(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store, account="teacher-other-ie")
    other = IntegrityError("INSERT", {}, Exception("fk_courses_created_by_users"))
    create_mock = AsyncMock(side_effect=other)
    monkeypatch.setattr(
        "app.services.courses.generate_invite_code",
        lambda: "ABCD2345",
    )
    monkeypatch.setattr(course_crud, "create_course_with_instructor", create_mock)

    with pytest.raises(IntegrityError):
        auth_client.post(
            "/api/v1/teacher/courses",
            headers={"Authorization": bearer},
            json={"name": "SE"},
        )
    assert create_mock.await_count == 1
    course_route_db.rollback.assert_awaited()
    course_route_db.commit.assert_not_awaited()


def test_create_course_invite_retries_exhausted_returns_503(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store, account="teacher-exhaust")
    create_mock = AsyncMock(side_effect=_invite_unique_integrity_error())
    monkeypatch.setattr(
        "app.services.courses.generate_invite_code",
        lambda: "ABCD2345",
    )
    monkeypatch.setattr(course_crud, "create_course_with_instructor", create_mock)

    response = auth_client.post(
        "/api/v1/teacher/courses",
        headers={"Authorization": bearer},
        json={"name": "SE"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Could not allocate invitation code; retry later"
    )
    assert create_mock.await_count == INVITE_COLLISION_RETRIES
    course_route_db.commit.assert_not_awaited()


def test_create_course_without_name_rejected(
    auth_client: TestClient, store: FakeStore
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    response = auth_client.post(
        "/api/v1/teacher/courses",
        headers={"Authorization": bearer},
        json={"name": "", "description": "x"},
    )
    assert response.status_code == 422


def test_list_courses_returns_counts(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login_teacher(auth_client, store)
    course_id = uuid4()
    course = SimpleNamespace(
        id=course_id,
        name="SE",
        description=None,
        invitation_code="ABCD2345",
        created_by=teacher.id,
    )
    list_mock = AsyncMock(return_value=[(course, 3, 2)])
    monkeypatch.setattr(course_crud, "list_courses_for_instructor", list_mock)

    response = auth_client.get(
        "/api/v1/teacher/courses",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "course_id": str(course_id),
            "name": "SE",
            "description": None,
            "invite_code": "ABCD2345",
            "student_count": 3,
            "topic_count": 2,
        }
    ]
    list_mock.assert_awaited_once_with(course_route_db, teacher.id)
    course_route_db.commit.assert_not_awaited()


def test_delete_by_creator_succeeds(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, teacher = _login_teacher(auth_client, store)
    course_id = uuid4()
    course = SimpleNamespace(id=course_id, created_by=teacher.id)
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    delete_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "delete_course", delete_mock)

    response = auth_client.delete(
        f"/api/v1/teacher/courses/{course_id}",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 204
    assert response.content == b""
    delete_mock.assert_awaited_once_with(course_route_db, course)
    course_route_db.commit.assert_awaited_once()


def test_non_creator_cannot_delete(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    course = SimpleNamespace(id=course_id, created_by=uuid4())
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    delete_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "delete_course", delete_mock)

    response = auth_client.delete(
        f"/api/v1/teacher/courses/{course_id}",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only the course creator can delete this course"
    )
    delete_mock.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


def test_delete_missing_course_is_idempotent(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=None))
    delete_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "delete_course", delete_mock)

    response = auth_client.delete(
        f"/api/v1/teacher/courses/{uuid4()}",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 204
    assert response.content == b""
    delete_mock.assert_not_awaited()
    course_route_db.commit.assert_not_awaited()


def test_create_requires_created_by_and_instructor_seed(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create must pass created_by into create_course_with_instructor."""
    bearer, teacher = _login_teacher(auth_client, store, account="teacher2")
    course_id = uuid4()
    create_mock = AsyncMock(
        return_value=SimpleNamespace(
            id=course_id,
            name="N",
            description=None,
            invitation_code="ZZZZZZZZ",
            created_by=teacher.id,
        )
    )
    monkeypatch.setattr(
        "app.services.courses.generate_invite_code",
        lambda: "ZZZZZZZZ",
    )
    monkeypatch.setattr(course_crud, "create_course_with_instructor", create_mock)

    response = auth_client.post(
        "/api/v1/teacher/courses",
        headers={"Authorization": bearer},
        json={"name": "N"},
    )
    assert response.status_code == 200
    assert create_mock.await_args == call(
        course_route_db,
        name="N",
        description=None,
        created_by=teacher.id,
        invitation_code="ZZZZZZZZ",
    )
