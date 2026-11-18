"""API tests for a teacher's provider key and default model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.core.enums import UserRole
from app.core.security import hash_token
from tests.api.v1.conftest import bearer_from, seed_user

_KNOWN_MODEL = "openai/gpt-6-luna"
_KNOWN_NAME = "GPT-6 Luna"


@dataclass
class _Row:
    api_key_hash: str | None = None
    masked_key: str | None = None
    key_updated_at: datetime | None = None
    default_model_id: str | None = None


@dataclass
class _Model:
    model_id: str
    name: str


class _Memory:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, _Row] = {}


def _install(monkeypatch: pytest.MonkeyPatch, memory: _Memory) -> None:
    catalog = {_KNOWN_MODEL: _Model(model_id=_KNOWN_MODEL, name=_KNOWN_NAME)}

    async def get_settings(_db, user_id: uuid.UUID) -> _Row | None:
        return memory.rows.get(user_id)

    async def get_inquiry_model(_db, model_id: str) -> _Model | None:
        return catalog.get(model_id)

    async def save_api_key(
        _db, user_id: uuid.UUID, api_key_hash: str, masked_key: str
    ) -> _Row:
        row = memory.rows.setdefault(user_id, _Row())
        row.api_key_hash = api_key_hash
        row.masked_key = masked_key
        row.key_updated_at = datetime.now(UTC)
        return row

    async def clear_api_key(_db, user_id: uuid.UUID) -> None:
        row = memory.rows.get(user_id)
        if row is not None:
            row.api_key_hash = None
            row.masked_key = None

    async def set_default_model(_db, user_id: uuid.UUID, model_id: str) -> None:
        row = memory.rows.setdefault(user_id, _Row())
        row.default_model_id = model_id

    target = "app.services.teacher_ai_settings.settings_crud"
    monkeypatch.setattr(f"{target}.get_settings", get_settings)
    monkeypatch.setattr(f"{target}.get_inquiry_model", get_inquiry_model)
    monkeypatch.setattr(f"{target}.save_api_key", save_api_key)
    monkeypatch.setattr(f"{target}.clear_api_key", clear_api_key)
    monkeypatch.setattr(f"{target}.set_default_model", set_default_model)


def _login(auth_client, account: str) -> str:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"account_id": account, "password": "password1"},
    )
    assert response.status_code == 200
    return bearer_from(response)


def _reject_raw_key(text: str, secret: str) -> None:
    stripped = secret.strip()
    if len(stripped) < 8:
        return
    if secret in text or stripped in text:
        raise AssertionError("response included the raw api key")


def _key(width: int) -> str:
    return "a" * width


def test_teacher_saves_reads_and_removes_key_and_keeps_default_model(
    auth_client, store, monkeypatch
) -> None:
    memory = _Memory()
    _install(monkeypatch, memory)
    seed_user(store, account_id="ai-teacher", role=UserRole.TEACHER)
    token = _login(auth_client, "ai-teacher")
    headers = {"Authorization": token}
    secret = _key(20)

    saved = auth_client.put(
        "/api/v1/users/me/ai/api-key",
        headers=headers,
        json={"api_key": f"  {secret}  "},
    )
    assert saved.status_code == 200
    _reject_raw_key(saved.text, secret)
    saved_body = saved.json()
    assert saved_body["configured"] is True
    assert saved_body["masked_key"] == "aaa...aaaa"
    assert saved_body["updated_at"]
    assert "api_key" not in saved_body
    stored = next(iter(memory.rows.values()))
    assert stored.api_key_hash == hash_token(secret)
    assert secret not in (stored.api_key_hash or "")

    chosen = auth_client.patch(
        "/api/v1/users/me/ai/model",
        headers=headers,
        json={"model_id": _KNOWN_MODEL},
    )
    assert chosen.status_code == 200
    assert chosen.json() == {
        "default_model": {"id": _KNOWN_MODEL, "name": _KNOWN_NAME},
        "message": "Default model updated",
    }

    current = auth_client.get("/api/v1/users/me/ai/settings", headers=headers)
    assert current.status_code == 200
    _reject_raw_key(current.text, secret)
    body = current.json()
    assert body["configured"] is True
    assert body["masked_key"] == "aaa...aaaa"
    assert body["default_model"] == {"id": _KNOWN_MODEL, "name": _KNOWN_NAME}
    assert "api_key" not in body

    removed = auth_client.delete("/api/v1/users/me/ai/api-key", headers=headers)
    assert removed.status_code == 204
    assert removed.content == b""

    after = auth_client.get("/api/v1/users/me/ai/settings", headers=headers)
    assert after.status_code == 200
    _reject_raw_key(after.text, secret)
    assert after.json()["configured"] is False
    assert after.json()["masked_key"] is None
    assert after.json()["default_model"] == {"id": _KNOWN_MODEL, "name": _KNOWN_NAME}


def test_delete_api_key_is_204_when_nothing_is_stored(
    auth_client, store, monkeypatch
) -> None:
    _install(monkeypatch, _Memory())
    seed_user(store, account_id="ai-empty", role=UserRole.TEACHER)
    token = _login(auth_client, "ai-empty")
    response = auth_client.delete(
        "/api/v1/users/me/ai/api-key",
        headers={"Authorization": token},
    )
    assert response.status_code == 204


@pytest.mark.parametrize(
    "kind",
    ["empty", "blank", "short", "long", "whitespace"],
)
def test_bad_api_key_is_422(auth_client, store, monkeypatch, kind: str) -> None:
    _install(monkeypatch, _Memory())
    seed_user(store, account_id=f"ai-bad-{kind}", role=UserRole.TEACHER)
    token = _login(auth_client, f"ai-bad-{kind}")
    secret = {
        "empty": "",
        "blank": "   ",
        "short": _key(19),
        "long": _key(257),
        "whitespace": "aaaa aaaaaaaaaaaaaaaa",
    }[kind]
    response = auth_client.put(
        "/api/v1/users/me/ai/api-key",
        headers={"Authorization": token},
        json={"api_key": secret},
    )
    _reject_raw_key(response.text, secret)
    assert response.status_code == 422


def test_unknown_model_is_422_and_known_model_succeeds(
    auth_client, store, monkeypatch
) -> None:
    _install(monkeypatch, _Memory())
    seed_user(store, account_id="ai-model", role=UserRole.TEACHER)
    token = _login(auth_client, "ai-model")
    headers = {"Authorization": token}

    unknown = auth_client.patch(
        "/api/v1/users/me/ai/model",
        headers=headers,
        json={"model_id": "openai/not-a-model"},
    )
    assert unknown.status_code == 422

    known = auth_client.patch(
        "/api/v1/users/me/ai/model",
        headers=headers,
        json={"model_id": _KNOWN_MODEL},
    )
    assert known.status_code == 200
    assert known.json()["default_model"]["id"] == _KNOWN_MODEL


def test_student_is_forbidden(auth_client, store, monkeypatch) -> None:
    _install(monkeypatch, _Memory())
    seed_user(store, account_id="ai-student", role=UserRole.USER)
    token = _login(auth_client, "ai-student")
    headers = {"Authorization": token}
    secret = _key(20)
    calls = [
        auth_client.get("/api/v1/users/me/ai/settings", headers=headers),
        auth_client.put(
            "/api/v1/users/me/ai/api-key",
            headers=headers,
            json={"api_key": secret},
        ),
        auth_client.delete("/api/v1/users/me/ai/api-key", headers=headers),
        auth_client.patch(
            "/api/v1/users/me/ai/model",
            headers=headers,
            json={"model_id": _KNOWN_MODEL},
        ),
    ]
    assert [call.status_code for call in calls] == [403, 403, 403, 403]
    _reject_raw_key("".join(call.text for call in calls), secret)


def test_missing_auth_on_reads_and_delete_is_401(auth_client, monkeypatch) -> None:
    _install(monkeypatch, _Memory())
    read = auth_client.get("/api/v1/users/me/ai/settings")
    removed = auth_client.delete("/api/v1/users/me/ai/api-key")
    assert read.status_code == 401
    assert removed.status_code == 401


def test_missing_auth_on_writes_is_401(auth_client, monkeypatch) -> None:
    _install(monkeypatch, _Memory())
    secret = _key(20)
    saved = auth_client.put(
        "/api/v1/users/me/ai/api-key",
        json={"api_key": secret},
    )
    chosen = auth_client.patch(
        "/api/v1/users/me/ai/model",
        json={"model_id": _KNOWN_MODEL},
    )
    _reject_raw_key(saved.text, secret)
    assert saved.status_code == 401
    assert chosen.status_code == 401
