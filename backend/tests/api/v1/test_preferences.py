"""API tests for PATCH /users/me/preferences."""

from __future__ import annotations

from tests.api.v1.conftest import bearer_from, seed_user


def _login(auth_client, account: str, password: str = "password1") -> str:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": password},
    )
    assert response.status_code == 200
    return bearer_from(response)


def test_patch_preferences_happy_paths(auth_client, store) -> None:
    seed_user(store, account_id="pref-user")
    token = _login(auth_client, "pref-user")

    for code in ("en", "es", "zh-TW"):
        response = auth_client.patch(
            "/api/v1/users/me/preferences",
            headers={"Authorization": token},
            json={"preferred_language": code},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["preferred_language"] == code
        assert "message" in body

        me = auth_client.get("/api/v1/users/me", headers={"Authorization": token})
        assert me.status_code == 200
        assert me.json()["preferred_language"] == code


def test_patch_preferences_unsupported_returns_invalid_language(
    auth_client, store
) -> None:
    seed_user(store, account_id="pref-invalid")
    token = _login(auth_client, "pref-invalid")

    response = auth_client.patch(
        "/api/v1/users/me/preferences",
        headers={"Authorization": token},
        json={"preferred_language": "fr"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid language code"

    me = auth_client.get("/api/v1/users/me", headers={"Authorization": token})
    assert me.json()["preferred_language"] == "zh-TW"


def test_patch_preferences_rejects_alias_codes(auth_client, store) -> None:
    seed_user(store, account_id="pref-alias")
    token = _login(auth_client, "pref-alias")

    response = auth_client.patch(
        "/api/v1/users/me/preferences",
        headers={"Authorization": token},
        json={"preferred_language": "en-US"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid language code"


def test_patch_preferences_allowed_when_must_change_password(
    auth_client, store
) -> None:
    seed_user(
        store,
        account_id="pref-mcp",
        must_change_password=True,
    )
    token = _login(auth_client, "pref-mcp")

    response = auth_client.patch(
        "/api/v1/users/me/preferences",
        headers={"Authorization": token},
        json={"preferred_language": "es"},
    )
    assert response.status_code == 200
    assert response.json()["preferred_language"] == "es"


def test_patch_preferences_unauthenticated(auth_client) -> None:
    response = auth_client.patch(
        "/api/v1/users/me/preferences",
        json={"preferred_language": "en"},
    )
    assert response.status_code == 401
