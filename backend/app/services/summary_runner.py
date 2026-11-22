"""Class synthesis, including report dependency waiting after teacher closure."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from uuid import UUID

from pydantic import ValidationError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.prompts import PromptStage, prompt_for
from app.crud import summary as summary_crud
from app.crud import topic as topic_crud
from app.services import ai_diagnostics
from app.services.attempt_lease import refresh
from app.services.central_synthesis import (
    MAX_PAYLOAD_BYTES,
    OUTPUT_SCHEMA,
    finalize,
    model_material,
    no_evidence_output,
    validate_reports,
)
from app.services.model_client import ModelCallError, OpenAIChatClient
from app.services.teacher_ai_settings import course_api_key
from app.services.token_budget import estimate_total_request_tokens

logger = logging.getLogger("app.model")
client = OpenAIChatClient()
_live: set[UUID] = set()
_tasks: set[asyncio.Task] = set()

_SCHEMA = OUTPUT_SCHEMA


def prepare_request(request: dict) -> tuple[list, dict, str]:
    if not request["reports"] and request.get("allow_empty_cohort"):
        reports = []
        material = {
            "interfaceLanguage": request["content_language"],
            "inquiry": {
                "theme": request["inquiry"]["theme"],
                "question": request["inquiry"]["inquiryQuestion"],
                "focus": request["inquiry"]["inquiryFocus"],
            },
            "reports": [],
        }
    else:
        reports = validate_reports(request["reports"])
        material = model_material(reports, request["content_language"])
    encoded = json.dumps(material, ensure_ascii=False)
    prompt = prompt_for(PromptStage.CLASS_SUMMARY)
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("Stage3 payload exceeds supported size")
    if (
        material["reports"]
        and estimate_total_request_tokens(
            model_id=request["model_id"],
            instructions=prompt.instructions,
            material=encoded,
            schema=_SCHEMA,
            output_tokens=prompt.max_output_tokens,
        )
        > settings.REPORT_CONTEXT_TOKEN_BUDGET
    ):
        raise ValueError("Stage3 request exceeds model budget")
    return reports, material, encoded


def live_attempts() -> set[UUID]:
    return set(_live)


def schedule(attempt_id: UUID) -> None:
    """Start summary preparation on the running event loop."""
    task = asyncio.get_running_loop().create_task(run_summary(attempt_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@ai_diagnostics.job_scope("summary")
async def run_summary(attempt_id: UUID) -> None:
    """Prepare one summary attempt and store it as ready or failed."""
    _live.add(attempt_id)
    refresher: asyncio.Task[None] | None = None
    prompt = prompt_for(PromptStage.CLASS_SUMMARY)
    try:
        request = await _begin(attempt_id)
        if request is None:
            return
        model_id = request["model_id"]
        refresher = asyncio.create_task(
            refresh(summary_crud.extend_lease, attempt_id, _live)
        )
        try:
            if request.get("schema_version") == "closed-stage2-v1":
                request = await _wait_for_reports(attempt_id, request)
            reports, material, encoded = prepare_request(request)
            if material["reports"]:
                parsed = await client.complete_object(
                    name="class_summary",
                    schema=_SCHEMA,
                    instructions=prompt.instructions,
                    material=encoded,
                    model=model_id,
                    max_tokens=prompt.max_output_tokens,
                    api_key=await _api_key(request["topic_id"]),
                )
            else:
                parsed = no_evidence_output(request["content_language"])
            draft = finalize(parsed, reports, request["content_language"])
            draft["native_synthesis"]["model_id"] = (
                model_id if material["reports"] else None
            )
            draft["native_synthesis"]["generation_method"] = (
                "model" if material["reports"] else "deterministic"
            )
            draft["native_synthesis"]["sources"] = request["sources"]
            draft["native_synthesis"]["prompt_version"] = prompt.version

        except (ModelCallError, ValueError, TypeError, KeyError) as exc:
            if isinstance(exc, ValidationError):
                ai_diagnostics.validation_failure("native_class_summary", exc)
            ai_diagnostics.emit(
                "job_validation_failed",
                error_type=type(exc).__name__,
                job_kind="summary",
            )
            await _fail(attempt_id)
            return
        await _ready(
            attempt_id,
            request["topic_id"],
            draft,
            prompt.stage.value,
            prompt.version,
        )
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
        if not await summary_crud.mark_processing(db, attempt_id):
            await db.commit()
            return None
        request = dict(attempt.request_json or {})
        if request.get("schema_version") not in {
            "native-central-request-v1",
            "closed-stage2-v1",
        }:
            await summary_crud.mark_failed(db, attempt_id)
            await db.commit()
            return None
        if "model_id" not in request:
            topic = await topic_crud.get_topic_by_id(db, attempt.topic_id)
            if topic is None:
                raise ValueError("Missing summary topic")
            request["model_id"] = topic.model_id or settings.OPENAI_MODEL
            request["content_language"] = (
                topic.content_language or settings.DEFAULT_LANGUAGE_CODE
            )
            attempt.request_json = dict(request)
        request["topic_id"] = attempt.topic_id
        await db.commit()
        return request


async def _api_key(topic_id: UUID) -> str | None:
    """The course teacher's key, or None for the single server key."""
    async with AsyncSessionLocal() as db:
        topic = await topic_crud.get_topic_by_id(db, topic_id)
        if topic is None:
            raise ValueError("Missing summary topic")
        return await course_api_key(db, topic.course_id)


async def _fail(attempt_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        await summary_crud.mark_failed(db, attempt_id)
        await db.commit()
    ai_diagnostics.emit("job_failed", job_kind="summary", job_id=str(attempt_id))
    logger.info("summary attempt failed")


async def _ready(
    attempt_id: UUID,
    topic_id: UUID,
    draft: dict,
    prompt_stage: str,
    prompt_version: str,
) -> None:
    async with AsyncSessionLocal() as db:
        await summary_crud.store_ready_summary(
            db,
            attempt_id=attempt_id,
            topic_id=topic_id,
            draft=draft,
            prompt_stage=prompt_stage,
            prompt_version=prompt_version,
        )
        await db.commit()


async def _wait_for_reports(attempt_id: UUID, request: dict) -> dict:
    from app.services.conversation_closure import prepare_closed_request

    deadline = asyncio.get_running_loop().time() + 600
    while asyncio.get_running_loop().time() < deadline:
        async with AsyncSessionLocal() as db:
            frozen = await prepare_closed_request(db, attempt_id, request)
        if frozen is not None:
            return frozen
        await asyncio.sleep(1)
    raise ValueError("Report preparation timed out; retry Stage2 transition")
