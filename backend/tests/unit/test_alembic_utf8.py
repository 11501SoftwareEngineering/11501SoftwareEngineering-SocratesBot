"""alembic.ini must load as UTF-8 even when the process locale is not UTF-8."""

from __future__ import annotations

from configparser import ConfigParser

import pytest
from alembic.config import Config

import app.core.alembic_utf8  # noqa: F401
from app.core.config import BACKEND_DIR


def test_cp950_cannot_decode_alembic_ini_utf8_comments() -> None:
    """Prove the Windows-locale failure mode against our UTF-8 alembic.ini."""
    parser = ConfigParser()
    with pytest.raises(UnicodeDecodeError):
        parser.read(BACKEND_DIR / "alembic.ini", encoding="cp950")


def test_alembic_config_loads_ini_with_chinese_comments() -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    assert config.get_main_option("script_location")
    ini_text = (BACKEND_DIR / "alembic.ini").read_text(encoding="utf-8")
    assert "請勿" in ini_text
