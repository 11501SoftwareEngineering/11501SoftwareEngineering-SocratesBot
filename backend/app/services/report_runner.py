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
from app.services.model_client import ModelCallError, OpenAIChatClient
from app.services.report_adapter import (
    NATIVE_SCHEMA,
    no_responses_summary,
    project_summary,
    source_digest,
    source_snapshot,
)
from app.services.report_text import validate_report
from app.services.teacher_ai_settings import course_api_key
from app.services.token_budget import estimate_total_request_tokens

logger = logging.getLogger("app.model")
client = OpenAIChatClient()
_live: set[UUID] = set()
_tasks: set[asyncio.Task] = set()

_SCHEMA = NATIVE_SCHEMA


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
    try:
        begun = await _begin(attempt_id)
        if begun is None:
            return
        session_id, progress = begun
        refresher = asyncio.create_task(
            refresh(report_crud.extend_lease, attempt_id, _live)
        )
        try:
            source = await _source(attempt_id, session_id, progress)
            model_id = source["model_id"]
            material = json.dumps(source["material"], ensure_ascii=False)
            if not source["exchanges"]:
                parsed = no_responses_summary(source["material"]["interfaceLanguage"])
            else:
                if (
                    estimate_total_request_tokens(
                        model_id=model_id,
                        instructions=prompt.instructions,
                        material=material,
                        schema=_SCHEMA,
                        output_tokens=prompt.max_output_tokens,
                    )
                    > settings.REPORT_CONTEXT_TOKEN_BUDGET
                ):
                    raise ValueError("Report source exceeds configured budget")
                api_key = await _api_key(session_id)
                parsed = await client.complete_object(
                    name="personal_report",
                    schema=_SCHEMA,
                    instructions=prompt.instructions,
                    material=material,
                    model=model_id,
                    max_tokens=prompt.max_output_tokens,
                    api_key=api_key,
                )
            body, native = project_summary(parsed, source)
            body = validate_report(body, source=source)
        except (ModelCallError, HTTPException, ValueError, TypeError):
            await _fail(attempt_id)
            return
        await _ready(
            attempt_id,
            body,
            prompt.stage.value,
            prompt.version,
            {
                "native_summary": native,
                "report_schema_version": "native-summary-v2",
                "model_id": model_id,
                "source_digest": source_digest(source),
            },
        )
    except Exception:
        logger.info("report attempt ended")
        await _fail(attempt_id)
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


async def _source(attempt_id: UUID, session_id: UUID, progress: dict | None) -> dict:
    async with AsyncSessionLocal() as db:
        attempt = await report_crud.get_attempt(db, attempt_id)
        if attempt is None or attempt.session_id != session_id:
            raise ValueError("Missing or mismatched report attempt")
        metadata = attempt.generation_meta or {}
        saved = metadata.get("report_source")
        if saved is not None:
            if source_digest(saved) != metadata.get("source_digest"):
                raise ValueError("Report source fingerprint mismatch")
            if "model_id" in saved:
                return saved
            # Upgrade historical snapshots once without replacing their evidence.
            from app.models.session import Session
            from app.models.topic import Topic

            session = await db.get(Session, session_id)
            topic = None if session is None else await db.get(Topic, session.topic_id)
            if topic is None:
                raise ValueError("Missing historical report topic")
            saved = {**saved, "model_id": topic.model_id or settings.OPENAI_MODEL}
            await report_crud.save_source(db, attempt_id, saved, source_digest(saved))
            await db.commit()
            return saved
        from app.models.session import Session

        session = await db.get(Session, session_id)
        if session is None:
            raise ValueError("Missing report session")
        loaded = await message_crud.load_owned_dialogue(
            db, session_id=session_id, user_id=session.user_id
        )
        if loaded is None:
            raise ValueError("Missing report dialogue")
        session, topic, messages = loaded
        source = source_snapshot(session, topic, messages, progress)
        await report_crud.save_source(db, attempt_id, source, source_digest(source))
        await db.commit()
        return source


async def _fail(attempt_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        await report_crud.mark_failed(db, attempt_id)
        await db.commit()
    logger.info("report attempt failed")


async def _ready(
    attempt_id: UUID,
    body: dict,
    prompt_stage: str,
    prompt_version: str,
    report_metadata: dict,
) -> None:
    async with AsyncSessionLocal() as db:
        await report_crud.mark_ready(
            db,
            attempt_id,
            body,
            prompt_stage=prompt_stage,
            prompt_version=prompt_version,
            report_metadata=report_metadata,
        )
        await db.commit()


async def _api_key(session_id: UUID) -> str | None:
    """Resolve credentials separately; never place them in the frozen evidence."""
    from app.models.session import Session
    from app.models.topic import Topic

    async with AsyncSessionLocal() as db:
        session = await db.get(Session, session_id)
        if session is None:
            raise ValueError("Missing report session")
        topic = await db.get(Topic, session.topic_id)
        if topic is None:
            raise ValueError("Missing report topic")
        return await course_api_key(db, topic.course_id)
