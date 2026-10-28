import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.enums import SessionStatus
from app.schemas.session import SessionData
from app.services.session import update_session_privacy


class FakeStore:
    def __init__(self, sessions: list[SessionData]) -> None:
        self.sessions = {session.id: session for session in sessions}
        self.updates: list[tuple[UUID, bool]] = []

    async def get_session(self, session_id: UUID) -> SessionData | None:
        return self.sessions.get(session_id)

    async def set_is_anonymous(
        self,
        session_id: UUID,
        is_anonymous: bool,
    ) -> SessionData:
        updated = replace(
            self.sessions[session_id],
            is_anonymous=is_anonymous,
        )
        self.sessions[session_id] = updated
        self.updates.append((session_id, is_anonymous))
        return updated


@pytest.mark.parametrize("is_anonymous", [True, False])
def test_owner_can_update_privacy(is_anonymous: bool) -> None:
    session = SessionData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status=SessionStatus.IN_PROGRESS,
        is_anonymous=not is_anonymous,
    )
    store = FakeStore([session])

    response = asyncio.run(
        update_session_privacy(
            store=store,
            session_id=session.id,
            current_user_id=session.user_id,
            is_anonymous=is_anonymous,
        )
    )

    assert response.session_id == session.id
    assert response.is_anonymous is is_anonymous
    assert response.message == "匿名分享設定已更新"
    assert store.sessions[session.id].is_anonymous is is_anonymous
    assert store.updates == [(session.id, is_anonymous)]


def test_non_owner_cannot_update_privacy() -> None:
    session = SessionData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status=SessionStatus.IN_PROGRESS,
        is_anonymous=False,
    )
    store = FakeStore([session])

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_session_privacy(
                store=store,
                session_id=session.id,
                current_user_id=uuid4(),
                is_anonymous=True,
            )
        )

    assert exc_info.value.status_code == 403
    assert store.sessions[session.id].is_anonymous is False
    assert store.updates == []


def test_missing_session_returns_404() -> None:
    store = FakeStore([])

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_session_privacy(
                store=store,
                session_id=uuid4(),
                current_user_id=uuid4(),
                is_anonymous=True,
            )
        )

    assert exc_info.value.status_code == 404
    assert store.updates == []
    assert store.sessions == {}


def test_session_deleted_before_update_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionData(
        id=uuid4(),
        topic_id=uuid4(),
        user_id=uuid4(),
        status=SessionStatus.IN_PROGRESS,
        is_anonymous=False,
    )
    store = FakeStore([session])

    async def delete_before_update(
        session_id: UUID,
        is_anonymous: bool,
    ) -> None:
        store.sessions.pop(session_id, None)
        return None

    monkeypatch.setattr(store, "set_is_anonymous", delete_before_update)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            update_session_privacy(
                store=store,
                session_id=session.id,
                current_user_id=session.user_id,
                is_anonymous=True,
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"
    assert store.sessions == {}
    assert store.updates == []
