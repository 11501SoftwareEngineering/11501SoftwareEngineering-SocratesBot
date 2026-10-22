"""Unit tests for STT prompt assembly."""

from __future__ import annotations

from app.core.locales import whisper_initial_prompt
from app.services.stt import build_stt_prompt


def test_zh_tw_steering_only_when_lexicon_empty() -> None:
    prompt = build_stt_prompt("zh-TW", lexicon_terms=[])
    assert prompt == whisper_initial_prompt("zh-TW")


def test_lexicon_before_steering_for_zh_tw() -> None:
    prompt = build_stt_prompt("zh-TW", lexicon_terms=["蘇格拉底", "辯證"])
    assert prompt is not None
    steering = whisper_initial_prompt("zh-TW")
    assert steering is not None
    assert prompt.index("蘇格拉底") < prompt.index(steering)
    assert prompt.endswith(steering) or steering in prompt


def test_en_lexicon_without_steering() -> None:
    prompt = build_stt_prompt("en", lexicon_terms=["Socrates", "dialectic"])
    assert prompt is not None
    assert "Socrates" in prompt
    assert whisper_initial_prompt("en") is None


def test_prompt_respects_max_chars() -> None:
    terms = [f"term{i:04d}" for i in range(200)]
    for max_chars in (25, 35, 45, 80):
        prompt = build_stt_prompt("en", lexicon_terms=terms, max_chars=max_chars)
        assert prompt is not None
        assert len(prompt) <= max_chars
