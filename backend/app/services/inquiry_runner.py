"""In-process inquiry generation. The request session is never used here."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.enums import ALLOWED_MAX_TURNS, AgeBand, GenerationStatus
from app.crud import attempt as attempt_crud
from app.services.model_client import ModelCallError, ModelClient, OpenAIChatClient

logger = logging.getLogger("app.model")

LEASE_SECONDS = 30
HEARTBEAT_SECONDS = 10
INSTRUCTIONS = (
    "Turn the teacher's notes into an eight-field inquiry. "
    "Return only the JSON object. Do not name a student. "
    "inquiry_focus must not prescribe a conclusion the student must accept. "
    "background_info must not state unverified claims as facts. "
    "Use exclusions 'unspecified' when the teacher gave no exclusion. "
    "opening_message may be empty."
)

client: ModelClient = OpenAIChatClient()
_live: set[UUID] = set()
_threads: dict[UUID, threading.Thread] = {}


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


def is_live(attempt_id: UUID) -> bool:
    return attempt_id in _live


def should_fail_processing(
    *,
    status: str,
    live: bool,
    lease_expires_at: datetime | None,
    now: datetime,
    startup: bool,
) -> bool:
    """A status read fails only an expired lease with no live task.

    Startup fails every processing row this process is not running.
    """
    if status != GenerationStatus.PROCESSING.value or live:
        return False
    if startup:
        return True
    if lease_expires_at is None:
        return False
    expires = lease_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires <= now


def schedule(attempt_id: UUID) -> None:
    thread = threading.Thread(
        target=_run_in_thread,
        args=(attempt_id,),
        name=f"inquiry-{attempt_id}",
        daemon=True,
    )
    _threads[attempt_id] = thread
    thread.start()


def join(attempt_id: UUID, timeout: float = 5) -> None:
    thread = _threads.get(attempt_id)
    if thread is not None:
        thread.join(timeout)


def _run_in_thread(attempt_id: UUID) -> None:
    try:
        asyncio.run(run_inquiry_attempt(attempt_id))
    except Exception:
        logger.info("inquiry attempt ended")


async def run_inquiry_attempt(attempt_id: UUID) -> None:
    _live.add(attempt_id)
    stop = asyncio.Event()
    heartbeat: asyncio.Task[None] | None = None
    try:
        request_json = await _begin_processing(attempt_id)
        if request_json is None:
            return
        heartbeat = asyncio.create_task(_heartbeat(attempt_id, stop))
        try:
            parsed = await client.complete_json(
                instructions=INSTRUCTIONS,
                material=json.dumps(request_json, ensure_ascii=False),
            )
            body = validate_inquiry_result(parsed)
        except (ModelCallError, ValueError, TypeError):
            await _fail(attempt_id)
            return
        await _ready(attempt_id, body)
    finally:
        stop.set()
        if heartbeat is not None:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
        _live.discard(attempt_id)


async def fail_orphaned_attempts() -> None:
    async with session_scope() as db:
        rows = await attempt_crud.list_processing(db)
        for row in rows:
            if is_live(row.id):
                continue
            await attempt_crud.mark_failed_if_processing(db, row.id)
        await db.commit()


def validate_inquiry_result(payload: dict) -> dict:
    required = (
        "age_band",
        "max_turns",
        "topic",
        "core_question",
        "inquiry_focus",
        "background_info",
        "exclusions",
        "opening_message",
    )
    if any(not isinstance(payload, dict) or key not in payload for key in required):
        raise ValueError("invalid inquiry object")
    age_band = payload["age_band"]
    max_turns = payload["max_turns"]
    if age_band not in {band.value for band in AgeBand}:
        raise ValueError("invalid inquiry object")
    if max_turns not in ALLOWED_MAX_TURNS:
        raise ValueError("invalid inquiry object")
    body: dict[str, object] = {"age_band": age_band, "max_turns": max_turns}
    for key in required[2:]:
        value = payload[key]
        if not isinstance(value, str):
            raise ValueError("invalid inquiry object")
        body[key] = value
    topic = str(body["topic"]).strip()
    question = str(body["core_question"]).strip()
    if not topic or not question:
        raise ValueError("invalid inquiry object")
    body["topic"] = topic
    body["core_question"] = question
    exclusions = str(body["exclusions"]).strip()
    body["exclusions"] = exclusions or "unspecified"
    return body


async def _begin_processing(attempt_id: UUID) -> dict | None:
    async with session_scope() as db:
        attempt = await attempt_crud.get_attempt(db, attempt_id)
        if attempt is None or attempt.status != GenerationStatus.PENDING.value:
            return None
        request_json = dict(attempt.request_json or {})
        await attempt_crud.mark_processing(db, attempt_id)
        await db.flush()
        await attempt_crud.refresh_lease(db, attempt_id, seconds=LEASE_SECONDS)
        await db.commit()
        return request_json


async def _fail(attempt_id: UUID) -> None:
    async with session_scope() as db:
        await attempt_crud.mark_failed_if_processing(db, attempt_id)
        await db.commit()


async def _ready(attempt_id: UUID, body: dict) -> None:
    async with session_scope() as db:
        await attempt_crud.mark_ready_if_processing(db, attempt_id, body)
        await db.commit()


async def _heartbeat(attempt_id: UUID, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_SECONDS)
            return
        except TimeoutError:
            pass
        try:
            async with session_scope() as db:
                await attempt_crud.refresh_lease(db, attempt_id, seconds=LEASE_SECONDS)
                await db.commit()
        except Exception:
            logger.info("inquiry lease refresh skipped")
