"""Real PostgreSQL cohort gating and native publication; no provider calls."""

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.crud import session as session_crud
from app.crud import summary as summary_crud
from app.models.course import CourseInstructor
from app.models.report_attempt import ReportAttempt
from app.models.session import Session
from app.models.user import User
from app.services import summaries, summary_runner
from app.services.central_synthesis import finalize, validate_reports
from tests.integration.test_session_crud import (
    create_course_and_topic,
    create_student,
    session_test_db,
)
from tests.unit.test_central_synthesis import metadata, output
from tests.unit.test_report_adapter import inputs

pytestmark = pytest.mark.integration


def test_native_cohort_publication_and_entry_gate(monkeypatch):
    monkeypatch.setattr(summary_runner, "schedule", lambda _id: None)

    async def run():
        async with session_test_db() as db:
            course, topic = await create_course_and_topic(db, stage="conversation")
            db.add(CourseInstructor(course_id=course.id, teacher_id=course.created_by))
            for key, value in vars(inputs()[1]).items():
                setattr(topic, key, value)
            student = await create_student(db)
            session = Session(topic_id=topic.id, user_id=student.id)
            db.add(session)
            await db.flush()
            teacher = await db.get(User, course.created_by)
            with pytest.raises(HTTPException) as caught:
                await summaries.start_summary(db, teacher=teacher, topic_id=topic.id)
            assert caught.value.status_code == 409
            session.outcome = "ended"
            session.ending_reason = "student_requested_stop"
            session.ended_at = datetime.now(UTC)
            await db.flush()
            with pytest.raises(HTTPException) as caught:
                await summaries.start_summary(db, teacher=teacher, topic_id=topic.id)
            assert caught.value.status_code == 409
            report = ReportAttempt(
                session_id=session.id,
                status="ready",
                result_json={"valid": "projection"},
                generation_meta=metadata(),
            )
            db.add(report)
            await db.flush()
            await summaries.start_summary(db, teacher=teacher, topic_id=topic.id)
            attempt = await summary_crud.latest_attempt(db, topic.id)
            assert attempt.request_json["sources"][0]["report_id"] == str(report.id)
            newcomer = await create_student(db)
            with pytest.raises(HTTPException) as caught:
                await session_crud.insert_session_id(
                    db, user_id=newcomer.id, topic_id=topic.id
                )
            assert caught.value.status_code == 409
            rows = validate_reports(attempt.request_json["reports"])
            draft = finalize(output(["report_1"]), rows, "en")
            draft["native_synthesis"]["sources"] = attempt.request_json["sources"]
            await summary_crud.mark_processing(db, attempt.id)
            await summary_crud.store_ready_summary(
                db,
                attempt_id=attempt.id,
                topic_id=topic.id,
                draft=draft,
                prompt_stage="class_summary",
                prompt_version="test",
            )
            await db.commit()
            assert topic.stage == "summary" and session.outcome == "ended"
            await summaries.review_summary(
                db,
                teacher=teacher,
                topic_id=topic.id,
                overview=draft["overview"],
                viewpoint_summary=draft["viewpoint_summary"],
            )
            await summaries.publish_summary(db, teacher=teacher, topic_id=topic.id)
            stored = await summary_crud.latest_summary(db, topic.id)
            assert stored.body["native_synthesis"]["totalReports"] == 1
            public = await summary_crud.published_document(db, topic.id)
            assert "native_synthesis" not in public and str(report.id) not in str(
                public
            )
            await summaries.edit_summary(
                db,
                teacher=teacher,
                topic_id=topic.id,
                overview="Teacher edited overview",
                viewpoint_summary=draft["viewpoint_summary"],
            )
            assert (await summary_crud.published_document(db, topic.id)) == public
            latest = await summary_crud.latest_summary(db, topic.id)
            assert latest.body["native_synthesis"] == stored.body["native_synthesis"]
            await summaries.withdraw_summary(db, teacher=teacher, topic_id=topic.id)
            assert await summary_crud.published_document(db, topic.id) is None

    asyncio.run(run())


def test_teacher_cutoff_zero_answer_report_and_automatic_summary(monkeypatch):
    from contextlib import asynccontextmanager

    from sqlalchemy import func, select

    from app.crud import message as message_crud
    from app.services import conversation_closure, report_runner, reports

    monkeypatch.setattr(report_runner, "schedule", lambda _id: None)
    monkeypatch.setattr(summary_runner, "schedule", lambda _id: None)

    async def run():
        async with session_test_db() as db:
            course, topic = await create_course_and_topic(db, stage="conversation")
            db.add(CourseInstructor(course_id=course.id, teacher_id=course.created_by))
            for key, value in vars(inputs()[1]).items():
                setattr(topic, key, value)
            student = await create_student(db)
            session = Session(topic_id=topic.id, user_id=student.id, goal_reached=False)
            db.add(session)
            await db.flush()
            teacher = await db.get(User, course.created_by)
            status = await conversation_closure.read_status(
                db, teacher=teacher, topic_id=topic.id
            )
            assert status["open_dialogue_count"] == 1
            with pytest.raises(HTTPException) as caught:
                await conversation_closure.close(
                    db, teacher=teacher, topic_id=topic.id, confirm=False
                )
            assert caught.value.status_code == 409
            result = await conversation_closure.close(
                db, teacher=teacher, topic_id=topic.id, confirm=True
            )
            assert result["stage2_closed"] and result["ended_dialogue_count"] == 1
            assert session.outcome == "ended" and not session.goal_reached
            assert (
                session.ending_reason == "teacher_ended_stage2"
                and session.completed_at is None
            )
            # The same row reload used by an in-flight reply sees the terminal cutoff.
            assert (await message_crud.lock_session(db, session.id)).outcome == "ended"
            other = await create_student(db)
            with pytest.raises(HTTPException) as entry:
                await session_crud.insert_session_id(
                    db, user_id=other.id, topic_id=topic.id
                )
            assert entry.value.status_code == 400
            personal = await db.scalar(
                select(ReportAttempt).where(ReportAttempt.session_id == session.id)
            )
            attempt = await summary_crud.latest_attempt(db, topic.id)

            @asynccontextmanager
            async def session_factory():
                yield db

            monkeypatch.setattr(report_runner, "AsyncSessionLocal", session_factory)
            monkeypatch.setattr(summary_runner, "AsyncSessionLocal", session_factory)
            await report_runner.run_report(personal.id)
            await db.refresh(personal)
            assert personal.status == "ready"
            individual = await reports.read_student_report(
                db, user_id=student.id, session_id=session.id
            )
            assert individual["report"]["evidence_status"] == "insufficient"
            assert individual["report"]["completed_turns"] == 0
            await summary_runner.run_summary(attempt.id)
            await db.refresh(attempt)
            assert attempt.status == "ready"
            draft = await summary_crud.latest_summary(db, topic.id)
            assert draft.body["denominator"] == 0 and draft.body["groups"] == []
            assert draft.body["published"] is None
            await conversation_closure.close(
                db, teacher=teacher, topic_id=topic.id, confirm=False
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(ReportAttempt)
                    .where(ReportAttempt.session_id == session.id)
                )
                == 1
            )

    asyncio.run(run())
