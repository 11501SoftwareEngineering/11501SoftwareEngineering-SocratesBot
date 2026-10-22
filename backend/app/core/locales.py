"""Supported locale codes for preference dropdown writes."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LANGUAGE_CODE = "zh-TW"


@dataclass(frozen=True, slots=True)
class SupportedLocale:
    code: str
    name: str


SUPPORTED_LOCALES: dict[str, SupportedLocale] = {
    "zh-TW": SupportedLocale(code="zh-TW", name="Traditional Chinese"),
    "en": SupportedLocale(code="en", name="English"),
    "es": SupportedLocale(code="es", name="Español"),
}


def parse_preference_language(raw: str) -> str:
    """Accept only canonical dropdown codes (``zh-TW`` / ``en`` / ``es``)."""
    if raw not in SUPPORTED_LOCALES:
        raise ValueError("invalid language")
    return raw
