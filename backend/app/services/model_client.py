"""OpenRouter Chat Completions over httpx. The key stays on the outbound header."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from typing import Any, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("app.model")
# A provider can ask for a long pause. This request does not wait past two seconds.
_MAX_RETRY_SECONDS = 2.0
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


_REPLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {"type": "string"},
        "goal_reached": {"type": "boolean"},
    },
    "required": ["reply", "goal_reached"],
}


class ModelClient(Protocol):
    async def complete_json(self, *, instructions: str, material: str) -> dict: ...

    async def complete_reply(
        self, *, instructions: str, material: str
    ) -> tuple[str, bool]: ...


class OpenAIChatClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def complete_json(
        self, *, instructions: str, material: str, model: str | None = None
    ) -> dict:
        return await self._post(
            name="inquiry_setup",
            schema=_INQUIRY_SCHEMA,
            instructions=instructions,
            material=material,
            model=model,
        )

    async def complete_object(
        self,
        *,
        name: str,
        schema: dict[str, Any],
        instructions: str,
        material: str,
    ) -> dict:
        return await self._post(
            name=name,
            schema=schema,
            instructions=instructions,
            material=material,
        )

    async def complete_reply(
        self, *, instructions: str, material: str
    ) -> tuple[str, bool]:
        parsed = await self._post(
            name="dialogue_reply",
            schema=_REPLY_SCHEMA,
            instructions=instructions,
            material=material,
        )
        reply = parsed.get("reply")
        goal_reached = parsed.get("goal_reached")
        if not isinstance(reply, str) or not isinstance(goal_reached, bool):
            raise ModelCallError(200)
        return reply, goal_reached

    async def _post(
        self,
        *,
        name: str,
        schema: dict[str, Any],
        instructions: str,
        material: str,
        model: str | None = None,
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
                    "name": name,
                    "strict": True,
                    "schema": schema,
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
        delay = float(raw)
    except ValueError:
        return None
    if not math.isfinite(delay) or delay < 0 or delay > _MAX_RETRY_SECONDS:
        return None
    return delay


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
