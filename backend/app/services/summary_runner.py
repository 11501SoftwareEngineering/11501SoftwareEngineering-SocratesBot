"""Class-summary generation. Stage changes only in the ready commit."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from contextlib import suppress
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.crud import summary as summary_crud
from app.services.attempt_lease import refresh
from app.services.model_client import ModelCallError, OpenAIChatClient
from app.services.summary_text import validate_summary

logger = logging.getLogger("app.model")
client = OpenAIChatClient()
_live: set[UUID] = set()

INSTRUCTIONS = (
    "Write a de-identified class summary from the name-free reports. "
    "Refer to reports only by their label. Do not include a student name, "
    "session id, or report id."
)

_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "overview": {"type": "string"},
        "viewpoint_summary": {"type": "string"},
        "denominator": {"type": "integer"},
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "conditions": {"type": "string"},
                    "count": {"type": "integer"},
                    "percentage": {"type": "number"},
                    "members": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "conditions", "count", "percentage", "members"],
            },
        },
        "ungrouped": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overview", "viewpoint_summary", "denominator", "groups", "ungrouped"],
}


def live_attempts() -> set[UUID]:
    return set(_live)


def schedule(attempt_id: UUID) -> None:
    """Start summary preparation on a daemon thread."""
    thread = threading.Thread(
        target=lambda: asyncio.run(run_summary(attempt_id)),
        name=f"summary-{attempt_id}",
        daemon=True,
    )
    thread.start()


async def run_summary(attempt_id: UUID) -> None:
    """Prepare one summary attempt and store it as ready or failed."""
    _live.add(attempt_id)
    refresher: asyncio.Task[None] | None = None
    try:
        request = await _begin(attempt_id)
        if request is None:
            return
        refresher = asyncio.create_task(
            refresh(summary_crud.extend_lease, attempt_id, _live)
        )
        try:
            parsed = await client.complete_object(
                name="class_summary",
                schema=_SCHEMA,
                instructions=INSTRUCTIONS,
                material=json.dumps(request["material"], ensure_ascii=False),
            )
            draft = validate_summary(parsed, request["labels"])
        except (ModelCallError, ValueError, TypeError, KeyError):
            await _fail(attempt_id)
            return
        await _ready(attempt_id, request["topic_id"], draft)
    except Exception:
        logger.info("summary attempt ended")
        await _fail(attempt_id)
    finally:
        if refresher is not None:
            refresher.cancel()
            with suppress(asyncio.CancelledError):
                await refresher
        _live.discard(attempt_id)


async def _begin(attempt_id: UUID) -> dict | None:
    async with AsyncSessionLocal() as db:
        attempt = await summary_crud.get_attempt(db, attempt_id)
        if attempt is None or attempt.status != "pending":
            return None
        request = dict(attempt.request_json or {})
        request["topic_id"] = attempt.topic_id
        await summary_crud.mark_processing(db, attempt_id)
        await db.commit()
        return request


async def _fail(attempt_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        await summary_crud.mark_failed(db, attempt_id)
        await db.commit()
    logger.info("summary attempt failed")


async def _ready(attempt_id: UUID, topic_id: UUID, draft: dict) -> None:
    async with AsyncSessionLocal() as db:
        await summary_crud.store_ready_summary(
            db, attempt_id=attempt_id, topic_id=topic_id, draft=draft
        )
        await db.commit()
