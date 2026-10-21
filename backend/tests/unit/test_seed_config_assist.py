"""Unit tests for seed config assist and db-reset confirmation."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import yaml

from scripts.confirm_db_reset import confirm_db_reset
from scripts.seed.catalog import ACCOUNT_ADMIN
from scripts.seed_config_assist import ensure_dev_admin_elevated


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
        stdin=StringIO("n\n"),
        stdout=StringIO(),
    )
    assert status == "skipped"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert data["SUPER_ADMIN_ACCOUNTS"] == ["alice"]


def test_config_assist_append_on_yes(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("SUPER_ADMIN_ACCOUNTS: [alice]\n", encoding="utf-8")
    status = ensure_dev_admin_elevated(
        config_path=config,
        example_path=tmp_path / "missing.example",
        prompt=True,
        stdin=StringIO("y\n"),
        stdout=StringIO(),
    )
    assert status == "appended"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert data["SUPER_ADMIN_ACCOUNTS"] == ["alice", ACCOUNT_ADMIN.account_id]


def test_confirm_db_reset_with_confirm_env() -> None:
    assert confirm_db_reset(confirm_env="1", stdout=StringIO()) is True


def test_confirm_db_reset_decline() -> None:
    assert (
        confirm_db_reset(
            confirm_env="",
            stdin=StringIO("n\n"),
            stdout=StringIO(),
        )
        is False
    )


def test_confirm_db_reset_accept() -> None:
    assert (
        confirm_db_reset(
            confirm_env="",
            stdin=StringIO("yes\n"),
            stdout=StringIO(),
        )
        is True
    )
