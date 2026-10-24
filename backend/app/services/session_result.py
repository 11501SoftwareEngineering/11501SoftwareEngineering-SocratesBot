from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.crud.session_result import SQLAlchemySessionResultStore
from app.schemas.session_result import (
    SessionResultData,
    SessionResultResponse,
)


class SessionResultStore(Protocol):
    async def get_session(self, session_id: UUID) -> SessionResultData | None:
        """Return session data, or None when the session does not exist."""
        ...


async def get_session_result(
    *,
    store: SessionResultStore,
    session_id: UUID,
    current_user_id: UUID,
) -> SessionResultResponse:
    session = await store.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the session owner",
        )

    if session.status != SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is not completed",
        )

    return SessionResultResponse(
        session_id=session.id,
        topic_id=session.topic_id,
    )


async def get_student_session_result(
    db: AsyncSession,
    current_user_id: UUID,
    session_id: UUID,
) -> SessionResultResponse:
    store = SQLAlchemySessionResultStore(db)

    return await get_session_result(
        store=store,
        session_id=session_id,
        current_user_id=current_user_id,
    )
