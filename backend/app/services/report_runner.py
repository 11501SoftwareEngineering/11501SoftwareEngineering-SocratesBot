"""Personal-report preparation. The request session is never used here."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from uuid import UUID

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.prompts import PromptStage, prompt_for
from app.crud import message as message_crud
from app.crud import report as report_crud
from app.services.attempt_lease import refresh
from app.services.dialogue_context import reply_material
from app.services.model_client import ModelCallError, OpenAIChatClient
from app.services.report_text import validate_report
from app.services.teacher_ai_settings import course_api_key

logger = logging.getLogger("app.model")
client = OpenAIChatClient()
_live: set[UUID] = set()
_tasks: set[asyncio.Task] = set()

_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "viewpoint_summary": {"type": "string"},
        "final_viewpoint": {"type": "string"},
        "viewpoint_status": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "strongest_reason": {"type": "string"},
        "challenges": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "challenge": {"type": "string"},
                    "responded": {"type": "boolean"},
                },
                "required": ["challenge", "responded"],
            },
        },
        "revision_or_defense": {"type": "string"},
        "focus_connection": {"type": "string"},
        "other_perspectives": {"type": "string"},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "evidence_status": {
            "type": "string",
            "enum": ["sufficient", "partial", "insufficient"],
        },
        "limitations": {"type": "string"},
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "turn": {"type": "integer"},
                    "question": {"type": "string"},
                    "evidence": {"type": "string"},
                    "viewpoint_before": {"type": "string"},
                    "viewpoint_after": {"type": "string"},
                    "change_type": {"type": "string"},
                    "attribution": {"type": "string"},
                },
                "required": [
                    "turn",
                    "question",
                    "evidence",
                    "viewpoint_before",
                    "viewpoint_after",
                    "change_type",
                    "attribution",
                ],
            },
        },
    },
    "required": [
        "viewpoint_summary",
        "final_viewpoint",
        "viewpoint_status",
        "reasons",
        "strongest_reason",
        "challenges",
        "revision_or_defense",
        "focus_connection",
        "other_perspectives",
        "open_questions",
        "evidence_status",
        "limitations",
        "timeline",
    ],
}


def live_attempts() -> set[UUID]:
    return set(_live)


def schedule(attempt_id: UUID) -> None:
    """Start report preparation on the running event loop."""
    task = asyncio.get_running_loop().create_task(run_report(attempt_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def run_report(attempt_id: UUID) -> None:
    """Prepare one report attempt and store it as ready or failed."""
    _live.add(attempt_id)
    refresher: asyncio.Task[None] | None = None
    prompt = prompt_for(PromptStage.PERSONAL_REPORT)
    model_id = settings.OPENAI_MODEL
    try:
        begun = await _begin(attempt_id)
        if begun is None:
            return
        session_id, progress = begun
        refresher = asyncio.create_task(
            refresh(report_crud.extend_lease, attempt_id, _live)
        )
        try:
            material, api_key = await _prepare(session_id, progress)
            parsed = await client.complete_object(
                name="personal_report",
                schema=_SCHEMA,
                instructions=prompt.instructions,
                material=material,
                model=model_id,
                max_tokens=prompt.max_output_tokens,
                api_key=api_key,
            )
            body = validate_report(parsed)
        # HTTPException: the course teacher's stored key cannot be decrypted.
        except (ModelCallError, HTTPException, ValueError, TypeError):
            await _fail(attempt_id)
            return
        await _ready(attempt_id, body, prompt.stage.value, prompt.version)
    finally:
        if refresher is not None:
            refresher.cancel()
            with suppress(asyncio.CancelledError):
                await refresher
        _live.discard(attempt_id)


async def _begin(attempt_id: UUID) -> tuple[UUID, dict | None] | None:
    async with AsyncSessionLocal() as db:
        attempt = await report_crud.get_attempt(db, attempt_id)
        if attempt is None or attempt.status != "pending":
            return None
        session_id = attempt.session_id
        progress = (attempt.generation_meta or {}).get("progress")
        await report_crud.mark_processing(db, attempt_id)
        await db.commit()
        return session_id, progress


async def _prepare(session_id: UUID, progress: dict | None) -> tuple[str, str | None]:
    """Return the report material and the course teacher's key (None: server pool)."""
    async with AsyncSessionLocal() as db:
        from app.models.session import Session
        from app.models.topic import Topic

        session = await db.get(Session, session_id)
        if session is None:
            raise ValueError("invalid report")
        topic = await db.get(Topic, session.topic_id)
        if topic is None:
            raise ValueError("invalid report")
        loaded = await message_crud.load_owned_dialogue(
            db, session_id=session_id, user_id=session.user_id
        )
        messages = [] if loaded is None else loaded[2]
        snapshot = json.dumps(progress, ensure_ascii=False) if progress else "null"
        material = f"{reply_material(topic, messages)}\nprogressSnapshot:\n{snapshot}"
        api_key = await course_api_key(db, topic.course_id)
        return material, api_key


async def _fail(attempt_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        await report_crud.mark_failed(db, attempt_id)
        await db.commit()
    logger.info("report attempt failed")


async def _ready(
    attempt_id: UUID, body: dict, prompt_stage: str, prompt_version: str
) -> None:
    async with AsyncSessionLocal() as db:
        await report_crud.mark_ready(
            db,
            attempt_id,
            body,
            prompt_stage=prompt_stage,
            prompt_version=prompt_version,
        )
        await db.commit()
