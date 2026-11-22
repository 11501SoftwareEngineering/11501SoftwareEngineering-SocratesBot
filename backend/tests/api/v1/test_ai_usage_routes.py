"""Usage is teacher-only and the owner is always the authenticated account."""

from unittest.mock import AsyncMock

from app.core.enums import UserRole
from app.services import ai_usage
from tests.api.v1.conftest import bearer_from, seed_user


def test_usage_read_is_authenticated_teacher_only(auth_client, store, monkeypatch):
    read = AsyncMock(return_value=ai_usage.aggregate([], "2026-11"))
    monkeypatch.setattr(ai_usage, "read_month", read)
    assert auth_client.get("/api/v1/users/me/ai/usage").status_code == 401
    for account, role, expected in [
        ("usage-student", UserRole.USER, 403),
        ("usage-teacher", UserRole.TEACHER, 200),
    ]:
        user = seed_user(store, account_id=account, role=role, name="Synthetic")
        login = auth_client.post(
            "/api/v1/auth/login", json={"account_id": account, "password": "password1"}
        )
        response = auth_client.get(
            "/api/v1/users/me/ai/usage", headers={"Authorization": bearer_from(login)}
        )
        assert response.status_code == expected
        assert len(response.headers["X-Request-ID"]) == 32
        if expected == 200:
            assert read.await_args.args[1] == user.id
            assert len(response.json()["by_stage"]) == 4
            assert response.json()["cost_usd"] is None
    read.assert_awaited_once()
