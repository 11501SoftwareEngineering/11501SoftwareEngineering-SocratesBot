"""Unit tests for supported locales (preference + STT)."""

from __future__ import annotations

import pytest

from app.core.locales import (
    DEFAULT_LANGUAGE_CODE,
    SUPPORTED_LOCALES,
    parse_preference_language,
    parse_stt_language,
    whisper_initial_prompt,
    whisper_language_hint,
)


def test_supported_locales_are_exactly_three() -> None:
    assert set(SUPPORTED_LOCALES) == {"zh-TW", "en", "es"}
    assert DEFAULT_LANGUAGE_CODE == "zh-TW"


@pytest.mark.parametrize("parse", [parse_preference_language, parse_stt_language])
def test_parse_exact_canonical_only(parse) -> None:
    assert parse("en") == "en"
    assert parse("zh-TW") == "zh-TW"
    assert parse("es") == "es"
    for raw in ("fr", "en-US", "zh-Hant", "zh_TW", " EN ", "es-ES"):
        with pytest.raises(ValueError, match="invalid"):
            parse(raw)


def test_whisper_zh_tw_steering() -> None:
    assert whisper_language_hint("zh-TW") == "zh"
    prompt = whisper_initial_prompt("zh-TW")
    assert prompt is not None
    assert "繁體" in prompt
    assert whisper_language_hint("en") == "en"
    assert whisper_initial_prompt("en") is None
