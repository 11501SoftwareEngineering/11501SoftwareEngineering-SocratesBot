"""Unit tests for development seed pack resolution and catalog."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.enums import UserRole
from scripts.seed.catalog import (
    ACCOUNT_ADMIN,
    CORE_ACCOUNTS,
    SHARED_PASSWORD,
    TOPIC_ID,
    credential_summary_lines,
)
from scripts.seed.packs import auth as auth_pack
from scripts.seed.runner import SeedError, require_development, resolve_packs


def test_resolve_packs_default_when_unset() -> None:
    assert resolve_packs(None) == ("auth", "course_graph")
    assert resolve_packs("") == ("auth", "course_graph")
    assert resolve_packs("   ") == ("auth", "course_graph")


def test_resolve_packs_override_single() -> None:
    assert resolve_packs("auth") == ("auth",)


def test_resolve_packs_unknown_raises() -> None:
    with pytest.raises(SeedError, match="unknown seed pack"):
        resolve_packs("auth,not_a_pack")


def test_require_development_rejects_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "test")
    with pytest.raises(SeedError, match="development only"):
        require_development()


def test_require_development_allows_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "development")
    require_development()


def test_catalog_shared_password_and_topic_id() -> None:
    assert SHARED_PASSWORD == "password1"
    assert str(TOPIC_ID) == "00000000-0000-4000-8000-000000000201"
    assert ACCOUNT_ADMIN.role is UserRole.TEACHER
    summary = "\n".join(credential_summary_lines())
    assert ACCOUNT_ADMIN.account_id in summary
    assert SHARED_PASSWORD in summary
    assert str(TOPIC_ID) in summary


def test_seed_auth_skips_hash_when_all_accounts_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _existing(_db: object, _account_id: str) -> object:
        return object()

    hash_mock = MagicMock(return_value="unused-hash")
    monkeypatch.setattr(auth_pack, "get_user_by_account", _existing)
    monkeypatch.setattr(auth_pack, "hash_password", hash_mock)
    monkeypatch.setattr(
        auth_pack,
        "ensure_default_language",
        AsyncMock(side_effect=AssertionError("should not create language")),
    )

    asyncio.run(auth_pack.seed_auth(MagicMock()))
    hash_mock.assert_not_called()
    assert len(CORE_ACCOUNTS) >= 1
