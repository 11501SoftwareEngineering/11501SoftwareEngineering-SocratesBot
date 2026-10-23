from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.api import deps as deps_mod
from app.core.database import get_db
from app.core.enums import UserRole
from app.crud import course as course_crud
from app.main import app
from app.models.course import Course


@pytest.fixture
def courses_client(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    async def provide_db():
        return object()

    monkeypatch.setitem(app.dependency_overrides, get_db, provide_db)
    return client


def override_user(
    monkeypatch: pytest.MonkeyPatch,
    *,
    role: UserRole,
) -> uuid.UUID:
    user_id = uuid.uuid4()

    async def provide_user():
        return SimpleNamespace(id=user_id, role=role.value)

    monkeypatch.setitem(
        app.dependency_overrides,
        deps_mod.get_current_active_user,
        provide_user,
    )
    return user_id


def test_teacher_can_create_course(
    courses_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    teacher_id = override_user(monkeypatch, role=UserRole.TEACHER)
    created_at = datetime.now(UTC)

    async def fake_create_course(
        _db,
        *,
        created_by,
        name: str,
        description: str | None,
    ) -> Course:
        assert created_by == teacher_id
        assert name == "測試課程"
        assert description == "建課測試"

        return Course(
            id=uuid.uuid4(),
            created_by=created_by,
            name=name,
            description=description,
            invitation_code="A1B2C3D4",
            created_at=created_at,
            updated_at=created_at,
        )

    monkeypatch.setattr(
        course_crud,
        "create_course",
        fake_create_course,
    )

    response = courses_client.post(
        "/api/v1/teacher/courses",
        json={
            "name": "測試課程",
            "description": "建課測試",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "測試課程"
    assert body["description"] == "建課測試"
    assert body["invite_code"] == "A1B2C3D4"
    assert "invitation_code" not in body
    assert "id" in body
    assert "created_at" in body


def test_regular_user_cannot_create_course(
    courses_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_user(monkeypatch, role=UserRole.USER)

    async def should_not_create_course(*args, **kwargs):
        raise AssertionError("非教師不應執行建課 CRUD")

    monkeypatch.setattr(
        course_crud,
        "create_course",
        should_not_create_course,
    )

    response = courses_client.post(
        "/api/v1/teacher/courses",
        json={"name": "不應建立的課程"},
    )

    assert response.status_code == 403


def test_create_course_rejects_empty_name(
    courses_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_user(monkeypatch, role=UserRole.TEACHER)

    response = courses_client.post(
        "/api/v1/teacher/courses",
        json={"name": ""},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("first_code", "second_code"),
    [
        ("AAAAAAAA", "BBBBBBBB"),
    ],
)
def test_create_course_retries_invitation_code_collision(
    monkeypatch: pytest.MonkeyPatch,
    first_code: str,
    second_code: str,
) -> None:
    codes = iter(first_code + second_code)
    monkeypatch.setattr(
        "app.crud.course.secrets.choice",
        lambda _alphabet: next(codes),
    )

    db = SimpleNamespace(
        scalar=AsyncMock(side_effect=[uuid.uuid4(), None]),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    course = __import__("asyncio").run(
        course_crud.create_course(
            db,
            created_by=uuid.uuid4(),
            name="碰撞測試",
            description=None,
        )
    )

    assert course.invitation_code == second_code
    assert db.scalar.await_count == 2
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(course)
