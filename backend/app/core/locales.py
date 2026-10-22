"""Supported locale codes for preference dropdown and STT language."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LANGUAGE_CODE = "zh-TW"

# Fullwidth Chinese punctuation is intentional for Whisper steering.
_ZH_TW_INITIAL_PROMPT = (
    "以下是繁體中文的蘇格拉底式課堂對話。請以繁體中文轉錄，勿使用簡體字。"  # noqa: RUF001
)


@dataclass(frozen=True, slots=True)
class SupportedLocale:
    code: str
    name: str
    whisper_language: str
    whisper_initial_prompt: str | None = None


SUPPORTED_LOCALES: dict[str, SupportedLocale] = {
    "zh-TW": SupportedLocale(
        code="zh-TW",
        name="Traditional Chinese",
        whisper_language="zh",
        whisper_initial_prompt=_ZH_TW_INITIAL_PROMPT,
    ),
    "en": SupportedLocale(
        code="en",
        name="English",
        whisper_language="en",
    ),
    "es": SupportedLocale(
        code="es",
        name="Español",
        whisper_language="es",
    ),
}


def parse_preference_language(raw: str) -> str:
    """Accept only canonical dropdown codes (``zh-TW`` / ``en`` / ``es``)."""
    if raw not in SUPPORTED_LOCALES:
        raise ValueError("invalid language")
    return raw


def parse_stt_language(raw: str) -> str:
    """Accept only canonical dropdown codes; raise ``ValueError`` when unsupported."""
    return parse_preference_language(raw)


def whisper_language_hint(code: str) -> str:
    return SUPPORTED_LOCALES[code].whisper_language


def whisper_initial_prompt(code: str) -> str | None:
    return SUPPORTED_LOCALES[code].whisper_initial_prompt
