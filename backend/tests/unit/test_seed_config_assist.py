"""Unit tests for seed config assist and db-reset confirmation."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
import yaml

from app.core.config import settings
from scripts.confirm_db_reset import confirm_db_reset
from scripts.seed.catalog import ACCOUNT_ADMIN
from scripts.seed_config_assist import ensure_dev_admin_elevated


@pytest.fixture
def development_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "development")


def test_config_assist_creates_from_example(tmp_path: Path) -> None:
    example = tmp_path / "config.yaml.example"
    example.write_text("SUPER_ADMIN_ACCOUNTS: [alice]\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    out = StringIO()
    status = ensure_dev_admin_elevated(
        config_path=config,
        example_path=example,
        prompt=False,
        stdout=out,
    )
    assert status == "created"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert data["SUPER_ADMIN_ACCOUNTS"] == [ACCOUNT_ADMIN.account_id]


def test_config_assist_unchanged_when_present(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        f"SUPER_ADMIN_ACCOUNTS: [{ACCOUNT_ADMIN.account_id}]\n",
        encoding="utf-8",
    )
    status = ensure_dev_admin_elevated(
        config_path=config,
        example_path=tmp_path / "missing.example",
        prompt=True,
        stdout=StringIO(),
    )
    assert status == "unchanged"


def test_config_assist_writes_empty_list(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("SUPER_ADMIN_ACCOUNTS: []\n", encoding="utf-8")
    status = ensure_dev_admin_elevated(
        config_path=config,
        example_path=tmp_path / "missing.example",
        prompt=True,
        stdout=StringIO(),
    )
    assert status == "wrote_empty"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert data["SUPER_ADMIN_ACCOUNTS"] == [ACCOUNT_ADMIN.account_id]


def test_config_assist_decline_leaves_file(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("SUPER_ADMIN_ACCOUNTS: [alice]\n", encoding="utf-8")
    status = ensure_dev_admin_elevated(
        config_path=config,
        example_path=tmp_path / "missing.example",
        prompt=True,
        stdin=StringIO("n"),
        stdout=StringIO(),
    )
    assert status == "skipped"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert data["SUPER_ADMIN_ACCOUNTS"] == ["alice"]


def test_config_assist_default_enter_is_no(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("SUPER_ADMIN_ACCOUNTS: [alice]\n", encoding="utf-8")
    status = ensure_dev_admin_elevated(
        config_path=config,
        example_path=tmp_path / "missing.example",
        prompt=True,
        stdin=StringIO("\n"),
        stdout=StringIO(),
    )
    assert status == "skipped"


def test_config_assist_append_on_yes(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("SUPER_ADMIN_ACCOUNTS: [alice]\n", encoding="utf-8")
    status = ensure_dev_admin_elevated(
        config_path=config,
        example_path=tmp_path / "missing.example",
        prompt=True,
        stdin=StringIO("y"),
        stdout=StringIO(),
    )
    assert status == "appended"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert data["SUPER_ADMIN_ACCOUNTS"] == ["alice", ACCOUNT_ADMIN.account_id]


def test_confirm_db_reset_with_confirm_env(development_env: None) -> None:
    out = StringIO()
    assert confirm_db_reset(confirm_env="1", stdout=out) is True
    assert "APP_ENV=development" in out.getvalue()


def test_confirm_db_reset_refuses_non_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "test")
    err = StringIO()
    assert confirm_db_reset(confirm_env="1", stdout=StringIO(), stderr=err) is False
    assert "development only" in err.getvalue()


def test_confirm_db_reset_decline(development_env: None) -> None:
    assert (
        confirm_db_reset(
            confirm_env="",
            stdin=StringIO("n"),
            stdout=StringIO(),
        )
        is False
    )


def test_confirm_db_reset_default_enter_is_no(development_env: None) -> None:
    assert (
        confirm_db_reset(
            confirm_env="",
            stdin=StringIO("\n"),
            stdout=StringIO(),
        )
        is False
    )


def test_confirm_db_reset_accept(development_env: None) -> None:
    out = StringIO()
    assert (
        confirm_db_reset(
            confirm_env="",
            stdin=StringIO("y"),
            stdout=out,
        )
        is True
    )
    assert "POSTGRES_HOST=" in out.getvalue()
