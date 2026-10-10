"""Auth API tests with an in-memory fake user store (no PostgreSQL required)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import deps as deps_mod
from app.core.cookies import CSRF_COOKIE, REFRESH_COOKIE
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.exceptions import AuthRequired
from app.core.redis import get_redis
from app.core.security import create_access_token, hash_password, verify_password
from app.crud.auth import RenewOutcome, RenewResult
from app.main import app


@dataclass
class FakePassword:
    password_hash: str
    must_change_password: bool = False


@dataclass
class FakeLanguage:
    code: str


@dataclass
class FakeUserLanguage:
    language: FakeLanguage


@dataclass
class FakeUser:
    id: uuid.UUID
    account_id: str
    name: str
    role: str
    password: FakePassword
    languages: list[FakeUserLanguage] = field(default_factory=list)


class FakeStore:
    def __init__(self) -> None:
        self.users_by_account: dict[str, FakeUser] = {}
        self.users_by_id: dict[uuid.UUID, FakeUser] = {}
        self.refresh_by_raw: dict[str, uuid.UUID] = {}


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def auth_client(client: TestClient, store: FakeStore, monkeypatch: pytest.MonkeyPatch):
    async def fake_get_user_by_account(_db, account_id: str):
        return store.users_by_account.get(account_id)

    async def fake_get_user_by_id(_db, user_id: uuid.UUID):
        return store.users_by_id.get(user_id)

    async def fake_create_user(
        _db,
        *,
        account_id: str,
        name: str,
        password: str,
        role: UserRole = UserRole.USER,
        must_change_password: bool = False,
    ):
        user = FakeUser(
            id=uuid.uuid4(),
            account_id=account_id,
            name=name,
            role=role.value,
            password=FakePassword(
                password_hash=hash_password(password),
                must_change_password=must_change_password,
            ),
            languages=[FakeUserLanguage(language=FakeLanguage(code="zh-TW"))],
        )
        store.users_by_account[account_id] = user
        store.users_by_id[user.id] = user
        return user

    def fake_preferred_language_code(user: FakeUser) -> str:
        if user.languages:
            return user.languages[0].language.code
        return "zh-TW"

    async def fake_create_refresh(_db, user_id: uuid.UUID) -> str:
        raw = f"refresh-{user_id}"
        store.refresh_by_raw[raw] = user_id
        return raw

    async def fake_get_active_user_id(_db, raw_refresh: str):
        return store.refresh_by_raw.get(raw_refresh)

    async def fake_revoke_all(_db, user_id: uuid.UUID) -> None:
        store.refresh_by_raw = {
            k: v for k, v in store.refresh_by_raw.items() if v != user_id
        }

    async def fake_renew(raw_refresh: str) -> RenewResult:
        user_id = store.refresh_by_raw.get(raw_refresh)
        if user_id is None:
            return RenewResult(outcome=RenewOutcome.REJECTED)
        new_raw = f"refresh-{user_id}-rotated"
        store.refresh_by_raw.pop(raw_refresh, None)
        store.refresh_by_raw[new_raw] = user_id
        return RenewResult(
            outcome=RenewOutcome.ROTATED,
            user_id=user_id,
            raw_refresh=new_raw,
            raw_csrf="csrf-rotated",
        )

    monkeypatch.setattr("app.crud.user.get_user_by_account", fake_get_user_by_account)
    monkeypatch.setattr("app.crud.user.get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr("app.crud.user.create_user", fake_create_user)
    monkeypatch.setattr(
        "app.crud.user.preferred_language_code", fake_preferred_language_code
    )
    monkeypatch.setattr("app.crud.auth.create_refresh_token", fake_create_refresh)
    monkeypatch.setattr(
        "app.crud.auth.get_active_user_id_for_refresh", fake_get_active_user_id
    )
    monkeypatch.setattr("app.crud.auth.revoke_all_for_user", fake_revoke_all)
    monkeypatch.setattr("app.crud.auth.renew_with_lock", fake_renew)

    class _Db:
        pass

    class _Redis:
        async def ping(self) -> bool:
            return True

    async def provide_db():
        return _Db()

    async def provide_redis():
        return _Redis()

    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_redis] = provide_redis
    yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_redis, None)


def _bearer(response) -> str:
    value = response.headers.get("authorization")
    assert value is not None
    assert value.lower().startswith("bearer ")
    return value


def test_register_login_and_me(auth_client: TestClient) -> None:
    register = auth_client.post(
        "/api/v1/auth/register",
        json={"account": "alice", "password": "password1", "name": "Alice"},
    )
    assert register.status_code == 200
    body = register.json()
    assert body["account"] == "alice"
    assert body["role"] == "USER"
    assert "message" in body
    assert "access_token" not in body

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"account": "alice", "password": "password1"},
    )
    assert login.status_code == 200
    token_body = login.json()
    assert "access_token" not in token_body
    assert token_body["must_change_password"] is False
    assert token_body["preferred_language"] == "zh-TW"
    assert token_body["role"] == "USER"
    assert "access_token" not in auth_client.cookies
    assert REFRESH_COOKIE in auth_client.cookies
    assert CSRF_COOKIE in auth_client.cookies
    bearer = _bearer(login)

    me = auth_client.get(
        "/api/v1/users/me",
        headers={"Authorization": bearer},
    )
    assert me.status_code == 200
    assert me.json() == {
        "account": "alice",
        "name": "Alice",
        "role": "USER",
        "preferred_language": "zh-TW",
    }


def test_me_silent_renew_on_get_without_bearer(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"account": "renew", "password": "password1", "name": "Renew"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"account": "renew", "password": "password1"},
    )
    # Cookies remain; no Authorization → GET silent-renews.
    me = auth_client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["account"] == "renew"
    _bearer(me)


def test_register_duplicate_account(auth_client: TestClient) -> None:
    payload = {"account": "bob", "password": "password1", "name": "Bob"}
    assert auth_client.post("/api/v1/auth/register", json=payload).status_code == 200
    again = auth_client.post("/api/v1/auth/register", json=payload)
    assert again.status_code == 409


def test_login_wrong_password(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"account": "carol", "password": "password1", "name": "Carol"},
    )
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"account": "carol", "password": "wrong-pass"},
    )
    assert response.status_code == 401


def test_me_requires_auth(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/users/me").status_code == 401


def test_logout_clears_session(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"account": "dave", "password": "password1", "name": "Dave"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"account": "dave", "password": "password1"},
    )
    csrf = auth_client.cookies.get(CSRF_COOKIE)
    assert csrf
    out = auth_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert out.status_code == 200
    assert auth_client.get("/api/v1/users/me").status_code == 401


def test_logout_csrf_mismatch_forbidden(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"account": "erin", "password": "password1", "name": "Erin"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"account": "erin", "password": "password1"},
    )
    out = auth_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": "not-the-cookie"},
    )
    assert out.status_code == 403


def test_logout_missing_csrf_cookie_forbidden(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"account": "frank", "password": "password1", "name": "Frank"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"account": "frank", "password": "password1"},
    )
    auth_client.cookies.pop(CSRF_COOKIE, None)
    out = auth_client.post("/api/v1/auth/logout")
    assert out.status_code == 403


def test_me_rejected_refresh_clears_cookies(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/v1/auth/register",
        json={"account": "gina", "password": "password1", "name": "Gina"},
    )
    auth_client.post(
        "/api/v1/auth/login",
        json={"account": "gina", "password": "password1"},
    )
    auth_client.cookies.set(REFRESH_COOKIE, "not-a-real-refresh")
    response = auth_client.get("/api/v1/users/me")
    assert response.status_code == 401
    set_cookie = ";".join(response.headers.get_list("set-cookie")).lower()
    assert REFRESH_COOKIE in set_cookie
    assert "max-age=0" in set_cookie


def test_write_method_does_not_silent_renew(
    store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = FakeUser(
        id=uuid.uuid4(),
        account_id="post-user",
        name="Post",
        role=UserRole.USER.value,
        password=FakePassword(password_hash=hash_password("password1")),
    )
    store.users_by_id[user.id] = user
    raw = f"refresh-{user.id}"
    store.refresh_by_raw[raw] = user.id

    async def fake_get_user_by_id(_db, user_id: uuid.UUID):
        return store.users_by_id.get(user_id)

    async def fake_renew(raw_refresh: str) -> RenewResult:
        raise AssertionError("renew must not run on POST")

    monkeypatch.setattr("app.crud.user.get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr("app.crud.auth.renew_with_lock", fake_renew)

    request = SimpleNamespace(
        method="POST",
        headers={},
        cookies={REFRESH_COOKIE: raw},
    )
    response = SimpleNamespace(headers={})
    with pytest.raises(AuthRequired):
        asyncio.run(
            deps_mod.get_current_user(request, response, db=object())  # type: ignore[arg-type]
        )


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("password1")
    assert verify_password("password1", hashed)
    assert not verify_password("nope", hashed)
    token = create_access_token(subject=uuid.uuid4(), role=UserRole.USER)
    assert isinstance(token, str) and token
