"""Real Postgres ending/enqueue persistence; no provider calls."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.crud import message as message_crud
from app.models.report_attempt import ReportAttempt
from app.models.session import Session
from app.services import dialogue, report_runner
from tests.integration.test_session_crud import create_course_and_topic, session_test_db

pytestmark = pytest.mark.integration


def test_finish_persists_one_pending_report_and_preserves_goal(monkeypatch):
    scheduled = []
    monkeypatch.setattr(report_runner, "schedule", scheduled.append)

    async def run():
        async with session_test_db() as db:
            course, topic = await create_course_and_topic(db, stage="conversation")
            session = Session(topic_id=topic.id, user_id=course.created_by)
            db.add(session)
            await db.flush()
            for _ in range(3):
                await message_crud.save_exchange(
                    db,
                    session_id=session.id,
                    content="I am uncertain.",
                    request_id=uuid4(),
                    reply="What makes you uncertain?",
                    goal_reached=False,
                    prompt_stage="dialogue",
                    prompt_version="test",
                )
            await db.commit()
            result = await dialogue.end_dialogue(
                db, user_id=session.user_id, session_id=session.id, action="finish"
            )
            assert result.report_eligible and not result.goal_reached
            await db.refresh(session)
            assert (
                session.outcome == "ended"
                and session.ending_reason == "student_requested_stop"
            )
            assert session.ended_at is not None and session.completed_at is None
            await dialogue.end_dialogue(
                db, user_id=session.user_id, session_id=session.id, action="finish"
            )
            rows = list(
                await db.scalars(
                    select(ReportAttempt).where(ReportAttempt.session_id == session.id)
                )
            )
            assert len(rows) == len(scheduled) == 1
            assert rows[0].status == "pending"

    asyncio.run(run())
