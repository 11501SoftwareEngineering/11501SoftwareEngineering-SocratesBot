"""Student course list / join / leave API tests (mocked CRUD)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.enums import UserRole
from app.crud import course as course_crud
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def _login_student(
    client: TestClient, store: FakeStore, account: str = "student1"
) -> tuple[str, object]:
    student = seed_user(store, account_id=account, name="Alice")
    login = client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": "password1"},
    )
    assert login.status_code == 200
    return bearer_from(login), student


def test_student_courses_require_auth(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/student/courses").status_code == 401


def test_teacher_blocked_from_student_routes(
    auth_client: TestClient, store: FakeStore
) -> None:
    teacher = seed_user(store, account_id="teacher1", role=UserRole.TEACHER, name="T")
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": teacher.account_id, "password": "password1"},
    )
    assert login.status_code == 200
    bearer = bearer_from(login)

    listed = auth_client.get(
        "/api/v1/student/courses", headers={"Authorization": bearer}
    )
    assert listed.status_code == 403
    assert listed.json()["detail"] == "Student privileges required"

    joined = auth_client.post(
        "/api/v1/student/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert joined.status_code == 403


def test_join_happy_path_creates_student_membership(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, student = _login_student(auth_client, store)
    course_id = uuid4()
    course = SimpleNamespace(
        id=course_id,
        name="SE",
        invitation_code="ABCD2345",
    )
    monkeypatch.setattr(
        course_crud,
        "get_course_by_invitation_code",
        AsyncMock(return_value=course),
    )
    monkeypatch.setattr(
        course_crud, "get_student_membership_row", AsyncMock(return_value=None)
    )
    add_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "add_student_membership", add_mock)

    response = auth_client.post(
        "/api/v1/student/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "abcd2345"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course_id),
        "name": "SE",
        "invite_code": "ABCD2345",
        "message": "Joined course",
    }
    add_mock.assert_awaited_once_with(
        course_route_db, course_id=course_id, user_id=student.id
    )
    course_route_db.commit.assert_awaited_once()


def test_join_invalid_format(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
) -> None:
    bearer, _ = _login_student(auth_client, store)
    response = auth_client.post(
        "/api/v1/student/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD!!!!"},
    )
    assert response.status_code == 422
    course_route_db.commit.assert_not_awaited()


def test_join_unknown_code(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_student(auth_client, store)
    monkeypatch.setattr(
        course_crud,
        "get_course_by_invitation_code",
        AsyncMock(return_value=None),
    )
    response = auth_client.post(
        "/api/v1/student/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == ("Course not found for this invitation code")


def test_join_duplicate_precheck(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_student(auth_client, store)
    course = SimpleNamespace(id=uuid4(), name="SE", invitation_code="ABCD2345")
    monkeypatch.setattr(
        course_crud,
        "get_course_by_invitation_code",
        AsyncMock(return_value=course),
    )
    monkeypatch.setattr(
        course_crud,
        "get_student_membership_row",
        AsyncMock(return_value=SimpleNamespace(left_at=None)),
    )
    add_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "add_student_membership", add_mock)

    response = auth_client.post(
        "/api/v1/student/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Already a member of this course"
    add_mock.assert_not_awaited()


def test_join_after_leave_rejected(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_student(auth_client, store)
    course = SimpleNamespace(id=uuid4(), name="SE", invitation_code="ABCD2345")
    monkeypatch.setattr(
        course_crud,
        "get_course_by_invitation_code",
        AsyncMock(return_value=course),
    )
    monkeypatch.setattr(
        course_crud,
        "get_student_membership_row",
        AsyncMock(return_value=SimpleNamespace(left_at=object())),
    )
    add_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "add_student_membership", add_mock)

    response = auth_client.post(
        "/api/v1/student/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot rejoin after leaving this course"
    add_mock.assert_not_awaited()


def test_join_duplicate_integrity_error(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_student(auth_client, store)
    course = SimpleNamespace(id=uuid4(), name="SE", invitation_code="ABCD2345")
    monkeypatch.setattr(
        course_crud,
        "get_course_by_invitation_code",
        AsyncMock(return_value=course),
    )
    monkeypatch.setattr(
        course_crud, "get_student_membership_row", AsyncMock(return_value=None)
    )
    orig = Exception("duplicate key value violates unique constraint")
    orig.constraint_name = "pk_course_memberships"  # type: ignore[attr-defined]
    monkeypatch.setattr(
        course_crud,
        "add_student_membership",
        AsyncMock(side_effect=IntegrityError("dup", {}, orig)),
    )

    response = auth_client.post(
        "/api/v1/student/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Already a member of this course"
    course_route_db.rollback.assert_awaited()
    course_route_db.commit.assert_not_awaited()


def test_leave_soft_deletes_membership(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, student = _login_student(auth_client, store)
    course_id = uuid4()
    soft_delete_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        course_crud, "soft_delete_student_membership_by_ids", soft_delete_mock
    )

    response = auth_client.delete(
        f"/api/v1/student/courses/{course_id}",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 204
    assert response.content == b""
    soft_delete_mock.assert_awaited_once_with(
        course_route_db, course_id=course_id, user_id=student.id
    )
    course_route_db.commit.assert_awaited_once()


def test_leave_when_not_member_is_idempotent(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, student = _login_student(auth_client, store)
    course_id = uuid4()
    soft_delete_mock = AsyncMock(return_value=False)
    monkeypatch.setattr(
        course_crud, "soft_delete_student_membership_by_ids", soft_delete_mock
    )
    response = auth_client.delete(
        f"/api/v1/student/courses/{course_id}",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 204
    assert response.content == b""
    soft_delete_mock.assert_awaited_once_with(
        course_route_db, course_id=course_id, user_id=student.id
    )
    course_route_db.commit.assert_not_awaited()


def test_list_active_topic_count_is_session_count(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, student = _login_student(auth_client, store)
    course_id = uuid4()
    course = SimpleNamespace(
        id=course_id,
        name="SE",
        invitation_code="ABCD2345",
    )
    list_mock = AsyncMock(return_value=[(course, "Teacher One", 2)])
    monkeypatch.setattr(course_crud, "list_student_courses", list_mock)

    response = auth_client.get(
        "/api/v1/student/courses",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "course_id": str(course_id),
            "name": "SE",
            "invite_code": "ABCD2345",
            "teacher_name": "Teacher One",
            "active_topic_count": 2,
        }
    ]
    list_mock.assert_awaited_once_with(course_route_db, student.id)
