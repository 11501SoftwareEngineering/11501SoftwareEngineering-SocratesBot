"""API tests for GET /users/me/ai/usage."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.enums import UserRole
from tests.api.v1.conftest import bearer_from, seed_user

URL = "/api/v1/users/me/ai/usage"


def _login(auth_client, account: str) -> str:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"account_id": account, "password": "password1"},
    )
    assert response.status_code == 200
    return bearer_from(response)


def _empty_stage(stage: str) -> dict:
    return {
        "stage": stage,
        "request_count": 0,
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": None,
    }


def test_teacher_reads_empty_month(auth_client, store) -> None:
    seed_user(store, account_id="usage-teacher", role=UserRole.TEACHER)
    token = _login(auth_client, "usage-teacher")

    response = auth_client.get(URL, headers={"Authorization": token})

    assert response.status_code == 200
    assert response.json() == {
        "month": datetime.now(UTC).strftime("%Y-%m"),
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "request_count": 0,
        "cost_usd": None,
        "cost_source": None,
        "updated_at": None,
        "by_stage": [
            _empty_stage("setup"),
            _empty_stage("dialogue"),
            _empty_stage("report"),
            _empty_stage("summary"),
        ],
    }


def test_non_teacher_forbidden(auth_client, store) -> None:
    seed_user(store, account_id="usage-student")
    token = _login(auth_client, "usage-student")

    response = auth_client.get(URL, headers={"Authorization": token})

    assert response.status_code == 403


def test_unauthenticated(auth_client) -> None:
    assert auth_client.get(URL).status_code == 401
