"""OpenRouter Chat Completions over httpx. The key stays on the outbound header."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("app.model")
# httpx debug logs can print the Authorization header.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

_INQUIRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "age_band": {
            "type": "string",
            "enum": ["13-15", "16-18", "university_plus"],
        },
        "max_turns": {"type": "integer", "enum": [5, 10, 15]},
        "topic": {"type": "string"},
        "core_question": {"type": "string"},
        "inquiry_focus": {"type": "string"},
        "background_info": {"type": "string"},
        "exclusions": {"type": "string"},
        "opening_message": {"type": "string"},
    },
    "required": [
        "age_band",
        "max_turns",
        "topic",
        "core_question",
        "inquiry_focus",
        "background_info",
        "exclusions",
        "opening_message",
    ],
}


class ModelCallError(Exception):
    """A provider failure. The message never includes the key or the reply text."""

    def __init__(self, status_code: int | None) -> None:
        self.status_code = status_code
        super().__init__("model call failed")


class ModelClient(Protocol):
    async def complete_json(self, *, instructions: str, material: str) -> dict: ...


class OpenAIChatClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def complete_json(
        self, *, instructions: str, material: str, model: str | None = None
    ) -> dict:
        key = settings.OPENAI_API_KEY.get_secret_value()
        payload = {
            "model": model or settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": material},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "inquiry_setup",
                    "strict": True,
                    "schema": _INQUIRY_SCHEMA,
                },
            },
        }
        response: httpx.Response | None = None
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=60.0
                ) as client:
                    response = await client.post(
                        f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {key}"},
                        json=payload,
                    )
            except httpx.HTTPError:
                logger.info("model provider status unavailable")
                raise ModelCallError(None) from None
            delay = _retry_delay(response)
            if (
                response.status_code in {429, 503}
                and attempt == 1
                and delay is not None
            ):
                if delay:
                    await asyncio.sleep(delay)
                continue
            break
        assert response is not None
        if response.status_code >= 400:
            logger.info("model provider status %s", response.status_code)
            raise ModelCallError(response.status_code) from None
        return _parse_completion(response)


def _retry_delay(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_completion(response: httpx.Response) -> dict:
    try:
        body = response.json()
        choice = body["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError
        message = choice["message"]
        content = message.get("content")
        if message.get("refusal") or not isinstance(content, str):
            raise ValueError
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        logger.info("model provider status %s", response.status_code)
        raise ModelCallError(response.status_code) from None
    if not isinstance(parsed, dict):
        logger.info("model provider status %s", response.status_code)
        raise ModelCallError(response.status_code) from None
    return parsed
