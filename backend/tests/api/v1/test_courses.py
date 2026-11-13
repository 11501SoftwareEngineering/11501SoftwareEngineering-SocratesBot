"""Course API tests: create / list / get / update / join / leave / members."""

from __future__ import annotations

from datetime import UTC, datetime
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
        json={"account_id": account, "password": "password1"},
    )
    assert login.status_code == 200
    return bearer_from(login), teacher


def test_courses_require_auth(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/courses").status_code == 401


def test_non_teacher_cannot_create_course(
    auth_client: TestClient, store: FakeStore
) -> None:
    student = seed_user(store, account_id="student1")
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account_id": student.account_id, "password": "password1"},
    )
    assert login.status_code == 200
    response = auth_client.post(
        "/api/v1/courses",
        headers={"Authorization": bearer_from(login)},
        json={"name": "SE"},
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
        "/api/v1/courses",
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
        "my_role": "teacher",
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
        "/api/v1/courses",
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
            "/api/v1/courses",
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
        "/api/v1/courses",
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
        "/api/v1/courses",
        headers={"Authorization": bearer},
        json={"name": "", "description": "x"},
    )
    assert response.status_code == 422


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
        f"/api/v1/courses/{course_id}",
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
        f"/api/v1/courses/{course_id}",
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
        f"/api/v1/courses/{uuid4()}",
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
        "/api/v1/courses",
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


# --- shared helpers for the role-based tests below ---------------------------


def _login(
    client: TestClient,
    store: FakeStore,
    account: str,
    role: UserRole = UserRole.USER,
    name: str = "User",
) -> tuple[str, object]:
    user = seed_user(store, account_id=account, name=name, role=role)
    login = client.post(
        "/api/v1/auth/login",
        json={"account_id": account, "password": "password1"},
    )
    assert login.status_code == 200
    return bearer_from(login), user


def _course(**overrides):
    base = {
        "id": uuid4(),
        "name": "SE",
        "description": "Fall",
        "invitation_code": "ABCD2345",
        "created_by": uuid4(),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_list_courses_merges_teaching_and_studying(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store, "both", UserRole.TEACHER)
    taught = _course(name="Taught", created_by=user.id)
    studied = _course(name="Studied", description=None)
    monkeypatch.setattr(
        course_crud,
        "list_instructed_courses",
        AsyncMock(return_value=[(taught, "Me", 2, 5)]),
    )
    monkeypatch.setattr(
        course_crud,
        "list_member_courses",
        AsyncMock(return_value=[((studied, "Other Teacher", 4, 30), "STUDENT")]),
    )

    response = auth_client.get("/api/v1/courses", headers={"Authorization": bearer})

    assert response.status_code == 200
    assert response.json() == [
        {
            "course_id": str(studied.id),
            "name": "Studied",
            "description": None,
            "teacher_name": "Other Teacher",
            "topic_count": 4,
            "my_role": "student",
            "my_permissions": [],
            "invite_code": "ABCD2345",
        },
        {
            "course_id": str(taught.id),
            "name": "Taught",
            "description": "Fall",
            "teacher_name": "Me",
            "topic_count": 2,
            "my_role": "teacher",
            "my_permissions": [],
            "invite_code": "ABCD2345",
            "student_count": 5,
        },
    ]


def test_list_courses_student_has_no_student_count(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "stud")
    monkeypatch.setattr(
        course_crud, "list_instructed_courses", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        course_crud,
        "list_member_courses",
        AsyncMock(return_value=[((_course(), "T", 1, 9), "STUDENT")]),
    )
    body = auth_client.get("/api/v1/courses", headers={"Authorization": bearer}).json()
    assert "student_count" not in body[0]


def test_old_role_prefixed_paths_are_gone(
    auth_client: TestClient, store: FakeStore
) -> None:
    bearer, _ = _login(auth_client, store, "old")
    for path in ("/student/courses", "/teacher/courses"):
        response = auth_client.get(f"/api/v1{path}", headers={"Authorization": bearer})
        assert response.status_code in (404, 405)


def test_get_course_returns_role_and_teacher_name(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "stud")
    course = _course()
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "get_course_role", AsyncMock(return_value="STUDENT")
    )
    monkeypatch.setattr(course_crud, "get_user_name", AsyncMock(return_value="Teacher"))

    response = auth_client.get(
        f"/api/v1/courses/{course.id}", headers={"Authorization": bearer}
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "SE",
        "description": "Fall",
        "teacher_name": "Teacher",
        "my_role": "student",
        "my_permissions": [],
        "invite_code": "ABCD2345",
    }


def test_get_course_non_member_is_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "outsider")
    monkeypatch.setattr(
        course_crud, "get_course_by_id", AsyncMock(return_value=_course())
    )
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=None))
    response = auth_client.get(
        f"/api/v1/courses/{uuid4()}", headers={"Authorization": bearer}
    )
    assert response.status_code == 404


def test_update_course_by_teacher(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course(created_by=user.id)
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=True)
    )

    response = auth_client.put(
        f"/api/v1/courses/{course.id}",
        headers={"Authorization": bearer},
        json={"name": "New", "description": None},
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "New",
        "description": None,
        "invite_code": "ABCD2345",
        "message": "Course updated",
    }
    course_route_db.commit.assert_awaited_once()


@pytest.mark.parametrize(
    ("body", "instructor", "exists", "expected"),
    [
        ({"name": ""}, True, True, 422),
        ({"name": "x"}, False, True, 403),
        ({"name": "x"}, True, False, 404),
    ],
)
def test_update_course_errors(
    body: dict,
    instructor: bool,
    exists: bool,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    monkeypatch.setattr(
        course_crud,
        "get_course_by_id",
        AsyncMock(return_value=_course() if exists else None),
    )
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=instructor)
    )
    response = auth_client.put(
        f"/api/v1/courses/{uuid4()}", headers={"Authorization": bearer}, json=body
    )
    assert response.status_code == expected
    course_route_db.commit.assert_not_awaited()


def _patch_join(monkeypatch, *, role, prior=None):
    course = _course()
    monkeypatch.setattr(
        course_crud, "get_course_by_invitation_code", AsyncMock(return_value=course)
    )
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=role))
    monkeypatch.setattr(
        course_crud, "get_student_membership_row", AsyncMock(return_value=prior)
    )
    add_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "add_student_membership", add_mock)
    return course, add_mock


def test_join_creates_student_membership(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store, "joiner")
    course, add_mock = _patch_join(monkeypatch, role=None)

    response = auth_client.post(
        "/api/v1/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "abcd2345"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "course_id": str(course.id),
        "name": "SE",
        "invite_code": "ABCD2345",
        "my_role": "student",
        "message": "Joined course",
    }
    add_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, user_id=user.id
    )


def test_teacher_account_cannot_join(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teacher-joiner", UserRole.TEACHER)
    _, add_mock = _patch_join(monkeypatch, role=None)
    response = auth_client.post(
        "/api/v1/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Student privileges required"
    add_mock.assert_not_awaited()


@pytest.mark.parametrize("role", ["TA", "STUDENT"])
def test_join_rejected_when_already_in_course(
    role: str,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "joiner")
    _, add_mock = _patch_join(monkeypatch, role=role)
    response = auth_client.post(
        "/api/v1/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 400
    add_mock.assert_not_awaited()


def test_join_after_leaving_is_rejected(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "leaver")
    _patch_join(monkeypatch, role=None, prior=SimpleNamespace(left_at=object()))
    response = auth_client.post(
        "/api/v1/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot rejoin after leaving this course"


def test_join_unknown_code_is_404(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "joiner")
    monkeypatch.setattr(
        course_crud, "get_course_by_invitation_code", AsyncMock(return_value=None)
    )
    response = auth_client.post(
        "/api/v1/courses/join",
        headers={"Authorization": bearer},
        json={"invite_code": "ABCD2345"},
    )
    assert response.status_code == 404


def test_student_leave_soft_deletes(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, user = _login(auth_client, store, "stud")
    course_id = uuid4()
    monkeypatch.setattr(
        course_crud, "get_course_role", AsyncMock(return_value="STUDENT")
    )
    leave_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        course_crud, "soft_delete_student_membership_by_ids", leave_mock
    )

    response = auth_client.delete(
        f"/api/v1/courses/{course_id}/member", headers={"Authorization": bearer}
    )

    assert response.status_code == 204
    leave_mock.assert_awaited_once_with(
        course_route_db, course_id=course_id, user_id=user.id
    )
    course_route_db.commit.assert_awaited_once()


@pytest.mark.parametrize("role", ["TEACHER", "TA"])
def test_teacher_or_ta_cannot_leave(
    role: str,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "staff", UserRole.TEACHER)
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=role))
    leave_mock = AsyncMock()
    monkeypatch.setattr(
        course_crud, "soft_delete_student_membership_by_ids", leave_mock
    )
    response = auth_client.delete(
        f"/api/v1/courses/{uuid4()}/member", headers={"Authorization": bearer}
    )
    assert response.status_code == 403
    leave_mock.assert_not_awaited()


def test_leave_when_not_member_is_idempotent(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "stud")
    monkeypatch.setattr(course_crud, "get_course_role", AsyncMock(return_value=None))
    monkeypatch.setattr(
        course_crud,
        "soft_delete_student_membership_by_ids",
        AsyncMock(return_value=False),
    )
    response = auth_client.delete(
        f"/api/v1/courses/{uuid4()}/member", headers={"Authorization": bearer}
    )
    assert response.status_code == 204
    course_route_db.commit.assert_not_awaited()


def _member_row(account: str):
    user = SimpleNamespace(id=uuid4(), account_id=account, name=account.title())
    membership = SimpleNamespace(joined_at=datetime(2026, 10, 1, tzinfo=UTC))
    return user, membership


def test_list_members_returns_students(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=True)
    )
    row = _member_row("alice")
    list_mock = AsyncMock(return_value=[row])
    monkeypatch.setattr(course_crud, "list_course_students", list_mock)

    response = auth_client.get(
        f"/api/v1/courses/{course.id}/members",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "student_id": str(row[0].id),
            "account_id": "alice",
            "name": "Alice",
            "joined_at": "2026-10-01T00:00:00Z",
        }
    ]
    list_mock.assert_awaited_once_with(course_route_db, course.id)


@pytest.mark.parametrize(
    ("instructor", "exists", "expected"),
    [(False, True, 403), (True, False, 404)],
)
def test_list_members_errors(
    instructor: bool,
    exists: bool,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    monkeypatch.setattr(
        course_crud,
        "get_course_by_id",
        AsyncMock(return_value=_course() if exists else None),
    )
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=instructor)
    )
    response = auth_client.get(
        f"/api/v1/courses/{uuid4()}/members",
        headers={"Authorization": bearer},
    )
    assert response.status_code == expected


def test_teacher_add_student_endpoint_still_works(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removed later together with the member-list rework (#169)."""
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    student = seed_user(store, account_id="alice", name="Alice")
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        course_crud, "get_student_membership", AsyncMock(return_value=None)
    )
    add_mock = AsyncMock()
    monkeypatch.setattr(course_crud, "add_student_membership", add_mock)

    response = auth_client.post(
        f"/api/v1/teacher/courses/{course.id}/students",
        headers={"Authorization": bearer},
        json={"account_id": "alice"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Student added"}
    add_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, user_id=student.id
    )


def test_remove_student_soft_deletes(
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    course = _course()
    target = uuid4()
    monkeypatch.setattr(course_crud, "get_course_by_id", AsyncMock(return_value=course))
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=True)
    )
    remove_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        course_crud, "soft_delete_student_membership_by_ids", remove_mock
    )

    response = auth_client.delete(
        f"/api/v1/courses/{course.id}/students/{target}",
        headers={"Authorization": bearer},
    )

    assert response.status_code == 204
    remove_mock.assert_awaited_once_with(
        course_route_db, course_id=course.id, user_id=target
    )
    course_route_db.commit.assert_awaited_once()


@pytest.mark.parametrize(
    ("instructor", "exists", "expected"),
    [(False, True, 403), (True, False, 404)],
)
def test_remove_student_errors(
    instructor: bool,
    exists: bool,
    expected: int,
    auth_client: TestClient,
    store: FakeStore,
    course_route_db: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer, _ = _login(auth_client, store, "teach", UserRole.TEACHER)
    monkeypatch.setattr(
        course_crud,
        "get_course_by_id",
        AsyncMock(return_value=_course() if exists else None),
    )
    monkeypatch.setattr(
        course_crud, "is_course_instructor", AsyncMock(return_value=instructor)
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        course_crud, "soft_delete_student_membership_by_ids", remove_mock
    )
    response = auth_client.delete(
        f"/api/v1/courses/{uuid4()}/students/{uuid4()}",
        headers={"Authorization": bearer},
    )
    assert response.status_code == expected
    remove_mock.assert_not_awaited()
