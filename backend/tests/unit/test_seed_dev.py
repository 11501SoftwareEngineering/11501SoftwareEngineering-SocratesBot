"""Unit tests for development seed pack resolution and catalog."""

from __future__ import annotations

import pytest

from scripts.seed.catalog import (
    ACCOUNT_ADMIN,
    SHARED_PASSWORD,
    TOPIC_ID,
    credential_summary_lines,
)
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
    summary = "\n".join(credential_summary_lines())
    assert ACCOUNT_ADMIN.account_id in summary
    assert SHARED_PASSWORD in summary
    assert str(TOPIC_ID) in summary
