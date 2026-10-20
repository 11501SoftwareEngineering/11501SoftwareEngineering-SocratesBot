from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status

from app.core.enums import SessionStatus
from app.schemas.session_result import SessionResultResponse


@dataclass(frozen=True)
class SessionResultData:
    id: UUID
    topic_id: UUID
    user_id: UUID
    status: SessionStatus
    is_anonymous: bool
    conclusion: str | None


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

    if session.conclusion is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session result is not available",
        )

    return SessionResultResponse(
        session_id=session.id,
        topic_id=session.topic_id,
        conclusion=session.conclusion,
        is_anonymous=session.is_anonymous,
    )
