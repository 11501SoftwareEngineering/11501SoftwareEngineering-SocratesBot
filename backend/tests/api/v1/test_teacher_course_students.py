"""Teacher roster list / add / remove API tests (mocked CRUD)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.enums import UserRole
from app.crud import course as course_crud
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def _login_teacher(
    client: TestClient, store: FakeStore, account: str = "roster-teacher"
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


def _patch_instructor_ok(monkeypatch: pytest.MonkeyPatch, *, course_id=None) -> None:
    course = SimpleNamespace(id=course_id or uuid4())
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=True)
    )


def test_list_students_empty_and_no_email(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    _patch_instructor_ok(monkeypatch, course_id=course_id)
    monkeypatch.setattr(course_crud, "list_course_students", AsyncMock(return_value=[]))

    response = auth_client.get(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_list_students_with_rows_no_email_key(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    student_id = uuid4()
    joined = datetime(2026, 10, 1, tzinfo=UTC)
    _patch_instructor_ok(monkeypatch, course_id=course_id)
    monkeypatch.setattr(
        course_crud,
        "list_course_students",
        AsyncMock(
            return_value=[
                (
                    SimpleNamespace(id=student_id, account_id="alice", name="Alice"),
                    SimpleNamespace(joined_at=joined),
                )
            ]
        ),
    )

    response = auth_client.get(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "student_id": str(student_id),
            "account_id": "alice",
            "name": "Alice",
            "joined_at": joined.isoformat().replace("+00:00", "Z"),
        }
    ]
    assert "email" not in body[0]


def test_add_student_by_account_id(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    student = seed_user(store, account_id="alice", name="Alice")
    _patch_instructor_ok(monkeypatch, course_id=course_id)
    monkeypatch.setattr(
        course_crud, "get_student_membership", AsyncMock(return_value=None)
    )
    add_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "add_student_membership", add_mock)

    response = auth_client.post(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
        json={"account_id": "alice"},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Student added"}
    add_mock.assert_awaited_once_with(
        course_route_db, course_id=course_id, user_id=student.id
    )
    course_route_db.commit.assert_awaited_once()


def test_add_duplicate_precheck(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    seed_user(store, account_id="alice")
    _patch_instructor_ok(monkeypatch, course_id=course_id)
    monkeypatch.setattr(
        course_crud,
        "get_student_membership",
        AsyncMock(return_value=SimpleNamespace()),
    )
    add_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "add_student_membership", add_mock)

    response = auth_client.post(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
        json={"account_id": "alice"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Student is already in this course"
    add_mock.assert_not_awaited()


def test_add_duplicate_integrity_error(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    seed_user(store, account_id="alice")
    _patch_instructor_ok(monkeypatch, course_id=course_id)
    monkeypatch.setattr(
        course_crud, "get_student_membership", AsyncMock(return_value=None)
    )
    orig = Exception("duplicate key value violates unique constraint")
    orig.constraint_name = "pk_course_memberships"  # type: ignore[attr-defined]
    monkeypatch.setattr(
        course_crud,
        "add_student_membership",
        AsyncMock(side_effect=IntegrityError("dup", {}, orig)),
    )

    response = auth_client.post(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
        json={"account_id": "alice"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Student is already in this course"
    course_route_db.rollback.assert_awaited()


def test_add_missing_account(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    _patch_instructor_ok(monkeypatch, course_id=course_id)

    response = auth_client.post(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
        json={"account_id": "nobody"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"


def test_add_teacher_account_rejected(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    seed_user(store, account_id="other-t", role=UserRole.TEACHER)
    _patch_instructor_ok(monkeypatch, course_id=course_id)

    response = auth_client.post(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
        json={"account_id": "other-t"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"


def test_non_instructor_forbidden(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    monkeypatch.setattr(
        course_crud,
        "get_course_by_id",
        AsyncMock(return_value=SimpleNamespace(id=course_id)),
    )
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=False)
    )

    response = auth_client.get(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Course not found"


def test_roster_missing_course_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=None))

    for method, path in (
        ("get", f"/api/v1/teacher/courses/{course_id}/students"),
        ("post", f"/api/v1/teacher/courses/{course_id}/students"),
        ("delete", f"/api/v1/teacher/courses/{course_id}/students/{uuid4()}"),
    ):
        kwargs: dict = {"headers": {"Authorization": bearer}}
        if method == "post":
            kwargs["json"] = {"account_id": "alice"}
        response = getattr(auth_client, method)(path, **kwargs)
        assert response.status_code == 404, path
        assert response.json()["detail"] == "Course not found"


def test_non_instructor_forbidden_on_add_and_remove(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    monkeypatch.setattr(
        course_crud,
        "get_course_by_id",
        AsyncMock(return_value=SimpleNamespace(id=course_id)),
    )
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=False)
    )

    add = auth_client.post(
        f"/api/v1/teacher/courses/{course_id}/students",
        headers={"Authorization": bearer},
        json={"account_id": "alice"},
    )
    assert add.status_code == 404
    assert add.json()["detail"] == "Course not found"

    remove = auth_client.delete(
        f"/api/v1/teacher/courses/{course_id}/students/{uuid4()}",
        headers={"Authorization": bearer},
    )
    assert remove.status_code == 404
    assert remove.json()["detail"] == "Course not found"


def test_remove_student_by_uuid(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    student_id = uuid4()
    _patch_instructor_ok(monkeypatch, course_id=course_id)
    delete_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        course_crud, "soft_delete_student_membership_by_ids", delete_mock
    )

    response = auth_client.delete(
        f"/api/v1/teacher/courses/{course_id}/students/{student_id}",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 204
    assert response.content == b""
    delete_mock.assert_awaited_once_with(
        course_route_db, course_id=course_id, user_id=student_id
    )
    course_route_db.commit.assert_awaited_once()


def test_remove_already_gone_student_is_idempotent(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login_teacher(auth_client, store)
    course_id = uuid4()
    _patch_instructor_ok(monkeypatch, course_id=course_id)
    monkeypatch.setattr(
        course_crud,
        "soft_delete_student_membership_by_ids",
        AsyncMock(return_value=False),
    )

    response = auth_client.delete(
        f"/api/v1/teacher/courses/{course_id}/students/{uuid4()}",
        headers={"Authorization": bearer},
    )
    assert response.status_code == 204
    assert response.content == b""
    course_route_db.commit.assert_not_awaited()
