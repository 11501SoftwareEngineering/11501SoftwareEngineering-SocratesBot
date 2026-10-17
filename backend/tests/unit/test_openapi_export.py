"""Unit tests for OpenAPI export without a running server or DB."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.export_openapi import (
    DUMMY_ENV,
    _postgres_password_env_key,
    ensure_export_env,
    export_openapi_dict,
    resolve_output_path,
    write_openapi_json,
)


def test_export_openapi_dict_includes_v1_paths() -> None:
    schema = export_openapi_dict()
    assert schema["openapi"].startswith("3.")
    paths = schema["paths"]
    assert any(p.startswith("/api/v1/") for p in paths)
    assert any("health" in p for p in paths)


def test_write_openapi_json_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    write_openapi_json(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "paths" in data
    assert data["openapi"].startswith("3.")


def test_exported_json_does_not_embed_dummy_jwt_secret(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    write_openapi_json(out)
    body = out.read_text(encoding="utf-8")
    assert DUMMY_ENV["JWT_SECRET_KEY"] not in body


def test_resolve_output_path_rejects_escape(tmp_path: Path) -> None:
    # Outside repo, cwd, and the process temp dir (pytest tmp lives under temp).
    outside = Path("/") / f"openapi-export-escape-{tmp_path.name}.json"
    with pytest.raises(ValueError, match="escapes allowed"):
        resolve_output_path(outside)


def test_resolve_output_path_allows_repo_relative(tmp_path: Path) -> None:
    # Default Make path is under the repo root (parent of backend/).
    from scripts import export_openapi as mod

    target = mod._REPO_ROOT / "docs" / "openapi" / "openapi.json"
    assert resolve_output_path(target) == target.resolve()


def test_settings_rejects_missing_jwt_when_env_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing required Settings fields fail clearly (export relies on ensure_export_env)."""
    from app.core.config import Settings, get_settings

    ensure_export_env()
    get_settings.cache_clear()
    for key in (*DUMMY_ENV, _postgres_password_env_key()):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]
