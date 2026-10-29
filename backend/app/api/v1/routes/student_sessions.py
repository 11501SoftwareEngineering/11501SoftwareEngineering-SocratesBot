from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, get_db
from app.api.openapi_responses import (
    SESSION_ENTRY_RESPONSES,
    SESSION_PRIVACY_RESPONSES,
    SESSION_RESULT_RESPONSES,
)
from app.schemas.session import (
    CreateSessionResponse,
    SessionResultResponse,
    UpdateSessionPrivacyRequest,
    UpdateSessionPrivacyResponse,
)
from app.services import session as session_service

router = APIRouter(prefix="/student", tags=["student-sessions"])


@router.post(
    "/topics/{topicId}/sessions",
    response_model=CreateSessionResponse,
    responses=SESSION_ENTRY_RESPONSES,
)
async def create_or_enter_student_session(
    topicId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreateSessionResponse:
    """Create or reuse the authenticated student's session for a topic."""
    return await session_service.create_or_enter_student_session(
        db,
        current_user.id,
        topicId,
    )


@router.patch(
    "/sessions/{sessionId}/privacy",
    response_model=UpdateSessionPrivacyResponse,
    responses=SESSION_PRIVACY_RESPONSES,
)
async def update_student_session_privacy(
    sessionId: UUID,
    payload: UpdateSessionPrivacyRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UpdateSessionPrivacyResponse:
    """Update the authenticated student's session privacy setting."""
    return await session_service.update_student_session_privacy(
        db,
        current_user.id,
        sessionId,
        payload.is_anonymous,
    )


@router.get(
    "/sessions/{sessionId}/result",
    response_model=SessionResultResponse,
    responses=SESSION_RESULT_RESPONSES,
)
async def get_student_session_result(
    sessionId: UUID,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResultResponse:
    """Return the authenticated student's completed session identifiers."""
    return await session_service.get_student_session_result(
        db,
        current_user.id,
        sessionId,
    )
