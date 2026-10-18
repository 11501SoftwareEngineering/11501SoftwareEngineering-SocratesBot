from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, get_db
from app.crud.session import SQLAlchemySessionStore
from app.schemas.session import CreateSessionResponse
from app.services import session as session_service

router = APIRouter(prefix="/student", tags=["student-sessions"])


@router.post("/topics/{topicId}/sessions", response_model=CreateSessionResponse)
async def create_or_enter_student_session(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateSessionResponse:
    """Create or reuse the authenticated student's session for a topic."""
    store = SQLAlchemySessionStore(
        db,
        initial_is_anonymous=False,
    )

    try:
        result = await session_service.create_or_enter_session(
            user_id=current_user.id,
            topic_id=topicId,
            store=store,
        )
        await db.commit()
    except session_service.TopicNotFoundError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        ) from exc
    except session_service.CourseAccessDeniedError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Course membership required",
        ) from exc
    except Exception:
        await db.rollback()
        raise

    return result
