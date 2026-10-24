import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.enums import SessionStatus
from app.crud.session_result import SQLAlchemySessionResultStore
from app.models.session import Session
from app.services.session_result import get_student_session_result
from tests.integration.test_session_crud import (
    create_course_and_topic,
    create_student,
    session_test_db,
)

pytestmark = pytest.mark.integration


def test_missing_session_returns_none() -> None:
    async def run() -> None:
        async with session_test_db() as db:
            store = SQLAlchemySessionResultStore(db)

            result = await store.get_session(uuid4())

            assert result is None

    asyncio.run(run())


@pytest.mark.parametrize(
    "session_status",
    [SessionStatus.IN_PROGRESS, SessionStatus.COMPLETED],
)
def test_get_session_returns_stored_values(
    session_status: SessionStatus,
) -> None:
    async def run() -> None:
        async with session_test_db() as db:
            _, topic = await create_course_and_topic(db)
            student = await create_student(db)

            topic_id = topic.id
            student_id = student.id

            session = Session(
                topic_id=topic_id,
                user_id=student_id,
                status=session_status.value,
                is_anonymous=False,
                completed_at=(
                    datetime.now(UTC)
                    if session_status == SessionStatus.COMPLETED
                    else None
                ),
            )
            db.add(session)
            await db.flush()
            session_id = session.id

            db.expunge_all()

            store = SQLAlchemySessionResultStore(db)
            result = await store.get_session(session_id)

            assert result is not None
            assert result.id == session_id
            assert result.topic_id == topic_id
            assert result.user_id == student_id
            assert result.status is session_status

    asyncio.run(run())


def test_owner_gets_completed_result_from_database() -> None:
    async def run() -> None:
        async with session_test_db() as db:
            _, topic = await create_course_and_topic(db)
            student = await create_student(db)

            topic_id = topic.id
            student_id = student.id

            session = Session(
                topic_id=topic_id,
                user_id=student_id,
                status=SessionStatus.COMPLETED.value,
                is_anonymous=False,
                completed_at=datetime.now(UTC),
            )
            db.add(session)
            await db.flush()
            session_id = session.id

            db.expunge_all()

            result = await get_student_session_result(
                db,
                student_id,
                session_id,
            )

            assert result.model_dump(mode="json") == {
                "session_id": str(session_id),
                "topic_id": str(topic_id),
            }

    asyncio.run(run())
