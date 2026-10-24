from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SessionStatus
from app.models.session import Session
from app.schemas.session_result import SessionResultData


async def get_session(
    db: AsyncSession,
    session_id: UUID,
) -> SessionResultData | None:
    session = await db.get(Session, session_id)

    if session is None:
        return None

    return SessionResultData(
        id=session.id,
        topic_id=session.topic_id,
        user_id=session.user_id,
        status=SessionStatus(session.status),
    )


class SQLAlchemySessionResultStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_session(
        self,
        session_id: UUID,
    ) -> SessionResultData | None:
        return await get_session(self._db, session_id)
