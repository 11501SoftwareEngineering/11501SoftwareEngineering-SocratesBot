import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.enums import SessionStatus
from app.services.session_result import SessionResultData, get_session_result


class FakeSessionResultStore:
    def __init__(self, sessions: dict[UUID, SessionResultData]) -> None:
        self.sessions = sessions

    async def get_session(self, session_id: UUID) -> SessionResultData | None:
        return self.sessions.get(session_id)


def test_owner_can_get_completed_session_result() -> None:
    session = SessionResultData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status=SessionStatus.COMPLETED,
    )
    store = FakeSessionResultStore({session.id: session})

    result = asyncio.run(
        get_session_result(
            store=store,
            session_id=session.id,
            current_user_id=session.user_id,
        )
    )

    assert result.model_dump(mode="json") == {
        "session_id": str(session.id),
        "topic_id": str(session.topic_id),
    }


@pytest.mark.parametrize(
    "session_status",
    [SessionStatus.IN_PROGRESS, SessionStatus.COMPLETED],
)
def test_non_owner_cannot_get_session_result(
    session_status: SessionStatus,
) -> None:
    session = SessionResultData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status=session_status,
    )
    store = FakeSessionResultStore({session.id: session})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_session_result(
                store=store,
                session_id=session.id,
                current_user_id=uuid4(),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not the session owner"


def test_missing_session_returns_404() -> None:
    store = FakeSessionResultStore({})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_session_result(
                store=store,
                session_id=uuid4(),
                current_user_id=uuid4(),
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"


def test_owner_cannot_get_in_progress_session_result() -> None:
    session = SessionResultData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status=SessionStatus.IN_PROGRESS,
    )
    store = FakeSessionResultStore({session.id: session})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_session_result(
                store=store,
                session_id=session.id,
                current_user_id=session.user_id,
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Session is not completed"
