"""Personal reports and the teaching read. A2 is not granted."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogueOutcome, GenerationStatus
from app.crud import course as course_crud
from app.crud import report as report_crud
from app.models.report_attempt import ReportAttempt
from app.models.session import Session
from app.models.topic import Topic
from app.models.user import User
from app.services import report_runner
from app.services.report_text import report_start, student_report

_NOT_COMPLETED = "Dialogue is not completed"


async def read_student_report(
    db: AsyncSession, *, user_id: UUID, session_id: UUID
) -> dict:
    session = await report_crud.owned_session(
        db, session_id=session_id, user_id=user_id
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if session.outcome != DialogueOutcome.COMPLETED.value:
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
    topic = await _instructor_topic(db, teacher, topic_id)
    session = await db.get(Session, session_id)
    if session is None or session.topic_id != topic.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return await _start(db, session)


async def read_teaching_reports(
    db: AsyncSession, *, teacher: User, topic_id: UUID
) -> dict:
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
        if session.outcome == DialogueOutcome.COMPLETED.value:
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
        "class_size": await report_crud.class_size(db, topic.course_id),
        "completed_count": completed_count,
        "ready_count": ready_count,
        "processing_count": processing_count,
        "failed_count": failed_count,
        "reports": reports,
    }


async def _start(db: AsyncSession, session: Session) -> dict:
    attempts = await report_crud.list_for_session(db, session.id)
    newest = attempts[-1].status if attempts else None
    action = report_start(session.outcome, newest)
    if action == "reject":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_NOT_COMPLETED)
    if action == "insert":
        created = await report_crud.insert_pending(db, session.id)
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
