"""Teacher-owned permanent Stage2 cutoff and asynchronous report-to-summary handoff."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud import report as report_crud
from app.crud import summary as summary_crud
from app.crud import topic as topic_crud
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User
from app.services import report_runner, reports, summaries, summary_runner
from app.services.dialogue_lifecycle import REPORT_OUTCOMES


async def status_body(db: AsyncSession, topic: Topic, *, ended_count: int = 0) -> dict:
    outcomes = list(
        await db.scalars(select(Session.outcome).where(Session.topic_id == topic.id))
    )
    latest = await summary_crud.latest_attempt(db, topic.id)
    return {
        "topic_id": topic.id,
        "topic_status": topic.stage,
        "open_dialogue_count": outcomes.count("open"),
        "stage2_closed": topic.stage == "summary",
        "confirmation_required": topic.stage == "conversation" and "open" in outcomes,
        "ended_dialogue_count": ended_count,
        "preparation_status": None if latest is None else latest.status,
    }


async def read_status(db: AsyncSession, *, teacher: User, topic_id: UUID) -> dict:
    topic = await summaries._instructor_topic(db, teacher, topic_id)
    return await status_body(db, topic)


async def close(
    db: AsyncSession, *, teacher: User, topic_id: UUID, confirm: bool
) -> dict:
    await summaries._instructor_topic(db, teacher, topic_id)
    topic = await topic_crud.lock_topic(db, topic_id)
    if topic is None:
        raise HTTPException(404, "Topic not found")
    if topic.stage == "setup":
        raise HTTPException(400, "Publish the activity before ending Stage2")
    # The topic lock serializes new entry; session locks serialize reply commits.
    sessions = list(
        await db.scalars(
            select(Session)
            .where(Session.topic_id == topic_id)
            .order_by(Session.id)
            .with_for_update()
        )
    )
    open_sessions = [session for session in sessions if session.outcome == "open"]
    if open_sessions and not confirm:
        raise HTTPException(
            409,
            {
                "code": "open_dialogues_confirmation_required",
                "open_dialogue_count": len(open_sessions),
                "message": "Confirm ending unfinished dialogues before closing Stage2",
            },
        )
    latest = await summary_crud.latest_attempt(db, topic_id)
    if (
        not open_sessions
        and latest is not None
        and (latest.status == "ready" or summaries._attempt_running(latest))
    ):
        return await status_body(db, topic)
    now = datetime.now(UTC)
    for session in open_sessions:
        session.outcome = "ended"
        session.ending_reason = "teacher_ended_stage2"
        session.ended_at = now
        session.awaiting_end_consent = False
        # goal_reached, legacy successful-completion status and completed_at are untouched.
    topic.stage = "summary"
    pending = []
    for session in sessions:
        if session.outcome in REPORT_OUTCOMES:
            created = await reports.queue_ending_report(
                db, session.id, (session.generation_meta or {}).get("progress")
            )
            if created is not None:
                pending.append(created.id)
    attempt = await summary_crud.insert_attempt(
        db,
        topic_id=topic_id,
        request_json={
            "schema_version": "closed-stage2-v1",
            "model_id": topic.model_id or settings.OPENAI_MODEL,
            "content_language": topic.content_language
            or settings.DEFAULT_LANGUAGE_CODE,
        },
    )
    await db.commit()
    for report_id in pending:
        report_runner.schedule(report_id)
    summary_runner.schedule(attempt.id)
    return await status_body(db, topic, ended_count=len(open_sessions))


async def prepare_closed_request(
    db: AsyncSession, attempt_id: UUID, request: dict
) -> dict | None:
    """None means healthy report jobs still running; failures require explicit retry."""
    topic = await topic_crud.lock_topic(db, request["topic_id"])
    latest = await summary_crud.latest_attempt(db, request["topic_id"])
    if (
        topic is None
        or topic.stage != "summary"
        or latest is None
        or latest.id != attempt_id
        or latest.status != "processing"
    ):
        raise ValueError("Stage2 transition was superseded or is no longer active")
    session_ids = list(
        await db.scalars(
            select(Session.id).where(
                Session.topic_id == topic.id,
                Session.outcome.in_(tuple(REPORT_OUTCOMES)),
            )
        )
    )
    attempts = await report_crud.list_for_sessions(db, session_ids)
    newest = {row.session_id: row for row in attempts}
    waiting = False
    for session_id in session_ids:
        row = newest.get(session_id)
        if row is None:
            raise ValueError("Missing personal report; retry the Stage2 transition")
        if row.status == "ready" and row.result_json:
            continue
        if reports._still_running(row):
            waiting = True
        else:
            raise ValueError(
                "Personal report failed or expired; retry the Stage2 transition"
            )
    if waiting:
        return None
    frozen = await summaries.native_request(
        db,
        topic,
        allow_empty=True,
        model_id=request["model_id"],
        language=request["content_language"],
    )
    latest.request_json = dict(frozen)
    await db.commit()
    return {**frozen, "topic_id": topic.id}
