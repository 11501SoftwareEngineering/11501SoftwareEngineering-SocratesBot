"""Personal reports and the teaching read. A2 is not granted."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GenerationStatus
from app.crud import course as course_crud
from app.crud import report as report_crud
from app.models.report_attempt import ReportAttempt
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User
from app.services import report_runner
from app.services.dialogue_lifecycle import REPORT_OUTCOMES
from app.services.report_text import report_start, student_report

_NOT_COMPLETED = "Dialogue is not report-eligible"


async def read_student_report(
    db: AsyncSession, *, user_id: UUID, session_id: UUID
) -> dict:
    """Return the caller's report after the dialogue is completed or ended.

    Raises:
        HTTPException: 404 if the session or report is missing; 409 if the
            dialogue is not report-eligible.
    """
    session = await report_crud.owned_session(
        db, session_id=session_id, user_id=user_id
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if session.outcome not in REPORT_OUTCOMES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_NOT_COMPLETED)
    attempts = await report_crud.list_for_session(db, session_id)
    if not attempts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    return await _payload(db, session, attempts)


async def start_student_report(
    db: AsyncSession, *, user_id: UUID, session_id: UUID
) -> dict:
    """Start the caller's report, or return the attempt already stored.

    Raises:
        HTTPException: 404 if the session is missing; 409 if the dialogue
            is not report-eligible.
    """
    session = await report_crud.owned_session(
        db, session_id=session_id, user_id=user_id
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return await _start(db, session)


async def start_teacher_retry(
    db: AsyncSession, *, teacher: User, topic_id: UUID, session_id: UUID
) -> dict:
    """Start another report for one report-eligible dialogue on this topic.

    Raises:
        HTTPException: 404 if the topic or session is missing; 403 if the
            caller does not instruct the course; 409 if the dialogue is
            not report-eligible.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    session = await db.get(Session, session_id)
    if session is None or session.topic_id != topic.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return await _start(db, session, compatibility_topic=topic)


async def read_teaching_reports(
    db: AsyncSession, *, teacher: User, topic_id: UUID
) -> dict:
    """Return ready reports for this topic, with the student's name.

    Raises:
        HTTPException: 404 if the topic is missing; 403 if the caller does
            not instruct the course.
    """
    topic = await _instructor_topic(db, teacher, topic_id)
    dialogues = await report_crud.topic_dialogues(db, topic.id)
    attempts = await report_crud.list_for_sessions(
        db, [session.id for session, _name in dialogues]
    )
    by_session: dict[UUID, list[ReportAttempt]] = {}
    for attempt in attempts:
        by_session.setdefault(attempt.session_id, []).append(attempt)
    reports = []
    ready_count = processing_count = failed_count = completed_count = 0
    for session, name in dialogues:
        if session.outcome == "completed":
            completed_count += 1
        rows = by_session.get(session.id, [])
        if not rows:
            continue
        newest = rows[-1]
        if newest.status in {
            GenerationStatus.PENDING.value,
            GenerationStatus.PROCESSING.value,
        }:
            processing_count += 1
        elif newest.status == GenerationStatus.FAILED.value:
            failed_count += 1
        ready = [
            row
            for row in rows
            if row.status == GenerationStatus.READY.value and row.result_json
        ]
        if not ready:
            continue
        ready_count += 1
        body = await _payload(db, session, rows)
        reports.append({**body, "student_display_name": name})
    return {
        "ended_count": sum(s.outcome == "ended" for s, _ in dialogues),
        "class_size": await report_crud.class_size(db, topic.course_id),
        "completed_count": completed_count,
        "ready_count": ready_count,
        "processing_count": processing_count,
        "failed_count": failed_count,
        "reports": reports,
    }


def _still_running(attempt: ReportAttempt) -> bool:
    if attempt.status not in {
        GenerationStatus.PENDING.value,
        GenerationStatus.PROCESSING.value,
    }:
        return False
    lease = attempt.lease_expires_at
    return lease is not None and lease >= datetime.now(UTC)


async def _start(
    db: AsyncSession, session: Session, *, compatibility_topic: Topic | None = None
) -> dict:
    await db.execute(select(Session).where(Session.id == session.id).with_for_update())
    attempts = await report_crud.list_for_session(db, session.id)
    newest = attempts[-1] if attempts else None
    status_value = None if newest is None else newest.status
    stale = status_value in {
        GenerationStatus.PENDING.value,
        GenerationStatus.PROCESSING.value,
    }
    if newest is not None and stale and not _still_running(newest):
        status_value = GenerationStatus.FAILED.value
    # Decide from the latest attempt AFTER acquiring the session lock. Another
    # retry may have produced a compatible report while we waited for the lock.
    if (
        compatibility_topic is not None
        and newest is not None
        and status_value == "ready"
    ):
        from app.services.central_synthesis import from_native, inquiry_key
        from app.services.dialogue_turn import brief_of

        try:
            report = from_native(str(newest.id), newest.generation_meta or {})
            if report.topicKey != inquiry_key(brief_of(compatibility_topic)):
                status_value = "failed"
        except (AttributeError, KeyError, ValueError, TypeError):
            status_value = "failed"
    action = report_start(session.outcome, status_value)
    if action == "reject":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_NOT_COMPLETED)
    if action == "insert":
        created = await report_crud.insert_pending(
            db,
            session.id,
            progress=(session.generation_meta or {}).get("progress"),
        )
        await db.commit()
        report_runner.schedule(created.id)
        attempts = await report_crud.list_for_session(db, session.id)
    return await _payload(db, session, attempts)


async def _payload(
    db: AsyncSession, session: Session, attempts: list[ReportAttempt]
) -> dict:
    ready = [
        row
        for row in attempts
        if row.status == GenerationStatus.READY.value and row.result_json
    ]
    body = ready[-1].result_json if ready else None
    report_id = str(ready[-1].id) if ready else None
    turns = await report_crud.student_turn_count(db, session.id)
    return student_report(
        status=attempts[-1].status,
        body=body,
        report_id=report_id,
        session_id=str(session.id),
        topic_id=str(session.topic_id),
        completed_turns=turns,
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
        ending_reason=getattr(session, "ending_reason", None) or "completed",
        ended_at=session.ended_at.isoformat()
        if getattr(session, "ended_at", None)
        else None,
        goal_reached=session.goal_reached,
    )


async def _instructor_topic(db: AsyncSession, teacher: User, topic_id: UUID) -> Topic:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
        )
    if not await course_crud.is_course_instructor(
        db, course_id=topic.course_id, teacher_id=teacher.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Course instructor required"
        )
    return topic


async def queue_ending_report(
    db: AsyncSession, session_id: UUID, progress: dict | None
):
    """Enqueue once in the ending transaction; caller schedules only after commit."""
    attempts = await report_crud.list_for_session(db, session_id)
    if attempts and (attempts[-1].status == "ready" or _still_running(attempts[-1])):
        return None
    return await report_crud.insert_pending(db, session_id, progress=progress)
