from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth_policies import AUTH_UNAUTHORIZED_DETAIL
from app.core.enums import SessionStatus, UserRole
from app.core.security import create_access_token
from app.crud import session_result as result_crud
from app.schemas.session_result import SessionResultData
from tests.api.v1.conftest import FakeStore, bearer_from, seed_user


def test_owner_can_get_completed_session_result(
    auth_client: TestClient,
    store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = seed_user(store, account_id="result-owner")

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": student.account_id, "password": "password1"},
    )
    assert login.status_code == 200

    session = SessionResultData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=student.id,
        status=SessionStatus.COMPLETED,
    )
    monkeypatch.setattr(
        result_crud,
        "get_session",
        AsyncMock(return_value=session),
    )

    response = auth_client.get(
        f"/api/v1/student/sessions/{session.id}/result",
        headers={"Authorization": bearer_from(login)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": str(session.id),
        "topic_id": str(session.topic_id),
    }


def test_get_result_requires_login(
    auth_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_mock = AsyncMock()
    monkeypatch.setattr(result_crud, "get_session", query_mock)

    response = auth_client.get(
        f"/api/v1/student/sessions/{uuid4()}/result",
    )

    assert response.status_code == 401
    assert response.json() == {"detail": AUTH_UNAUTHORIZED_DETAIL}
    assert response.headers["www-authenticate"] == "Bearer"
    query_mock.assert_not_awaited()


def test_missing_session_returns_404(
    auth_client: TestClient,
    store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = seed_user(store, account_id="result-missing")

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": student.account_id, "password": "password1"},
    )
    assert login.status_code == 200

    monkeypatch.setattr(
        result_crud,
        "get_session",
        AsyncMock(return_value=None),
    )

    response = auth_client.get(
        f"/api/v1/student/sessions/{uuid4()}/result",
        headers={"Authorization": bearer_from(login)},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found"}


@pytest.mark.parametrize(
    "session_status",
    [SessionStatus.IN_PROGRESS, SessionStatus.COMPLETED],
)
def test_non_owner_cannot_get_session_result(
    session_status: SessionStatus,
    auth_client: TestClient,
    store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = seed_user(store, account_id="result-non-owner")

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": student.account_id, "password": "password1"},
    )
    assert login.status_code == 200

    session = SessionResultData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status=session_status,
    )
    monkeypatch.setattr(
        result_crud,
        "get_session",
        AsyncMock(return_value=session),
    )

    response = auth_client.get(
        f"/api/v1/student/sessions/{session.id}/result",
        headers={"Authorization": bearer_from(login)},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not the session owner"}


def test_owner_cannot_get_in_progress_session_result(
    auth_client: TestClient,
    store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = seed_user(store, account_id="result-in-progress")

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": student.account_id, "password": "password1"},
    )
    assert login.status_code == 200

    session = SessionResultData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=student.id,
        status=SessionStatus.IN_PROGRESS,
    )
    monkeypatch.setattr(
        result_crud,
        "get_session",
        AsyncMock(return_value=session),
    )

    response = auth_client.get(
        f"/api/v1/student/sessions/{session.id}/result",
        headers={"Authorization": bearer_from(login)},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Session is not completed"}


def test_invalid_session_id_returns_422(
    auth_client: TestClient,
    store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = seed_user(store, account_id="result-invalid-id")

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": student.account_id, "password": "password1"},
    )
    assert login.status_code == 200

    query_mock = AsyncMock()
    monkeypatch.setattr(result_crud, "get_session", query_mock)

    response = auth_client.get(
        "/api/v1/student/sessions/not-a-uuid/result",
        headers={"Authorization": bearer_from(login)},
    )

    assert response.status_code == 422
    query_mock.assert_not_awaited()


def test_expired_token_without_refresh_returns_401(
    auth_client: TestClient,
    store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = seed_user(store, account_id="result-expired")

    expired_token = create_access_token(
        subject=student.id,
        role=UserRole.USER,
        expires_delta=timedelta(minutes=-1),
    )

    query_mock = AsyncMock()
    monkeypatch.setattr(result_crud, "get_session", query_mock)

    response = auth_client.get(
        f"/api/v1/student/sessions/{uuid4()}/result",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": AUTH_UNAUTHORIZED_DETAIL}
    assert response.headers["www-authenticate"] == "Bearer"
    query_mock.assert_not_awaited()
