"""Unit tests for supported preference locales."""

from __future__ import annotations

import pytest

from app.core.locales import (
    DEFAULT_LANGUAGE_CODE,
    SUPPORTED_LOCALES,
    parse_preference_language,
)


def test_supported_locales_are_exactly_three() -> None:
    assert set(SUPPORTED_LOCALES) == {"zh-TW", "en", "es"}
    assert DEFAULT_LANGUAGE_CODE == "zh-TW"


def test_parse_preference_language_exact_canonical_only() -> None:
    assert parse_preference_language("en") == "en"
    assert parse_preference_language("zh-TW") == "zh-TW"
    assert parse_preference_language("es") == "es"
    for raw in ("fr", "en-US", "zh-Hant", "zh_TW", " EN ", "es-ES"):
        with pytest.raises(ValueError, match="invalid"):
            parse_preference_language(raw)
