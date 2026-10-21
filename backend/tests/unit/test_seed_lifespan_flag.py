"""Unit tests for SEED_DEV_DATA settings and DB-only lifespan seed entry."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from scripts.seed import runner as seed_runner


def test_seed_dev_data_defaults_false() -> None:
    field = Settings.model_fields["SEED_DEV_DATA"]
    assert field.default is False


def test_run_seed_db_does_not_write_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan / CLI DB entry must never touch config.yaml (KTD8 / AE4)."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("SUPER_ADMIN_ACCOUNTS: []\n", encoding="utf-8")
    before = config_path.read_text(encoding="utf-8")

    def _fail_if_called(**_kwargs: object) -> str:
        msg = "config assist must not run on DB-only seed path"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "scripts.seed_config_assist.ensure_dev_admin_elevated",
        _fail_if_called,
    )

    async def _noop(_db: object) -> None:
        return None

    monkeypatch.setitem(seed_runner.PACK_REGISTRY, "auth", _noop)

    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(seed_runner, "AsyncSessionLocal", MagicMock(return_value=cm))
    monkeypatch.setattr(seed_runner, "warn_if_admin_not_elevated", lambda: None)

    with patch("scripts.seed_config_assist._write_mapping") as write_mock:
        asyncio.run(seed_runner.run_seed_db(packs=("auth",), print_summary=False))
        write_mock.assert_not_called()

    assert config_path.read_text(encoding="utf-8") == before
