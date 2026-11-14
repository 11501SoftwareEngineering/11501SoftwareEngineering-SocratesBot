"""Personal-report preparation. The request session is never used here."""

from __future__ import annotations

import asyncio
import logging
import threading
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.crud import message as message_crud
from app.crud import report as report_crud
from app.services.dialogue import reply_material
from app.services.model_client import ModelCallError, OpenAIChatClient
from app.services.report_text import validate_report

logger = logging.getLogger("app.model")
client = OpenAIChatClient()
_live: set[UUID] = set()

INSTRUCTIONS = (
    "Write a personal inquiry report from the dialogue. "
    "Do not include a student name, user id, session id, or report id. "
    "Use exclusions 'unspecified' when none were given."
)

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


def schedule(attempt_id: UUID) -> None:
    """Start report preparation on a daemon thread."""
    thread = threading.Thread(
        target=lambda: asyncio.run(run_report(attempt_id)),
        name=f"report-{attempt_id}",
        daemon=True,
    )
    thread.start()


async def run_report(attempt_id: UUID) -> None:
    """Prepare one report attempt and store it as ready or failed."""
    _live.add(attempt_id)
    try:
        session_id = await _begin(attempt_id)
        if session_id is None:
            return
        try:
            material = await _material(session_id)
            parsed = await client.complete_object(
                name="personal_report",
                schema=_SCHEMA,
                instructions=INSTRUCTIONS,
                material=material,
            )
            body = validate_report(parsed)
        except (ModelCallError, ValueError, TypeError):
            await _fail(attempt_id)
            return
        await _ready(attempt_id, body)
    finally:
        _live.discard(attempt_id)


async def _begin(attempt_id: UUID) -> UUID | None:
    async with AsyncSessionLocal() as db:
        attempt = await report_crud.get_attempt(db, attempt_id)
        if attempt is None or attempt.status != "pending":
            return None
        session_id = attempt.session_id
        await report_crud.mark_processing(db, attempt_id)
        await db.commit()
        return session_id


async def _material(session_id: UUID) -> str:
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
        return reply_material(topic, messages)


async def _fail(attempt_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        await report_crud.mark_failed(db, attempt_id)
        await db.commit()
    logger.info("report attempt failed")


async def _ready(attempt_id: UUID, body: dict) -> None:
    async with AsyncSessionLocal() as db:
        await report_crud.mark_ready(db, attempt_id, body)
        await db.commit()
