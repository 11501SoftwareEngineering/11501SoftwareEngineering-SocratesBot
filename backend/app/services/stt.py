"""Student STT: prompt assembly, Transcriber protocol, Fake + Groq adapters."""

# ruff: noqa: RUF001 — Whisper prompts intentionally use CJK fullwidth punctuation.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fastapi import HTTPException, status
from groq import APIConnectionError, APIStatusError, APITimeoutError, AsyncGroq

from app.api.student_audio_errors import (
    STT_CONNECTION_FAILED_DETAIL,
    STT_PROVIDER_FAILED_DETAIL,
    STT_TIMEOUT_DETAIL,
)
from app.core.config import settings
from app.core.locales import whisper_initial_prompt, whisper_language_hint

GROQ_MODEL = "whisper-large-v3-turbo"
PROMPT_MAX_CHARS = 800


def build_stt_prompt(
    locale_code: str,
    lexicon_terms: list[str] | None = None,
    *,
    max_chars: int = PROMPT_MAX_CHARS,
) -> str | None:
    """Lexicon first, Traditional steering last so truncation keeps script bias."""
    steering = whisper_initial_prompt(locale_code) or ""
    terms = (
        lexicon_terms if lexicon_terms is not None else list(settings.STT_LEXICON_TERMS)
    )

    sep = "、" if locale_code == "zh-TW" else ", "
    prefix = "專有名詞：" if locale_code == "zh-TW" else "Terms: "

    budget = max_chars - len(steering) - (1 if steering else 0)
    kept: list[str] = []
    used = len(prefix) if terms else 0
    for raw in terms:
        term = raw.strip()
        if not term or term in kept:
            continue
        cost = len(term) + (len(sep) if kept else 0)
        if used + cost > budget:
            break
        kept.append(term)
        used += cost

    lexicon_part = f"{prefix}{sep.join(kept)}。" if kept else ""
    if lexicon_part and steering:
        return f"{lexicon_part} {steering}".strip()
    return lexicon_part or steering or None


class Transcriber(Protocol):
    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str,
        prompt: str | None,
        api_key: str,
    ) -> str: ...


@dataclass
class FakeTranscriber:
    """Deterministic STT for API tests; records the last call."""

    text: str = "fake transcript"
    last_call: dict[str, object] | None = field(default=None, init=False)

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str,
        prompt: str | None,
        api_key: str,
    ) -> str:
        self.last_call = {
            "audio_len": len(audio_bytes),
            "filename": filename,
            "content_type": content_type,
            "language": language,
            "prompt": prompt,
            "api_key": api_key,
            "whisper_language": whisper_language_hint(language),
        }
        return self.text


class GroqTranscriber:
    """Groq Whisper via official AsyncGroq; key from the request only."""

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        language: str,
        prompt: str | None,
        api_key: str,
    ) -> str:
        client = AsyncGroq(
            api_key=api_key,
            max_retries=3,
            timeout=30.0,
        )
        try:
            result = await client.audio.transcriptions.create(
                model=GROQ_MODEL,
                file=(filename, audio_bytes, content_type),
                language=whisper_language_hint(language),
                prompt=prompt or "",
                temperature=0,
            )
        except APITimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=STT_TIMEOUT_DETAIL,
            ) from exc
        except APIConnectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=STT_CONNECTION_FAILED_DETAIL,
            ) from exc
        except APIStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=STT_PROVIDER_FAILED_DETAIL,
            ) from exc
        return (getattr(result, "text", None) or "").strip()


def get_transcriber() -> Transcriber:
    return GroqTranscriber()
