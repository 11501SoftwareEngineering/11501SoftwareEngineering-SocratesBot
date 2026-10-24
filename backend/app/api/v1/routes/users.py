from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, get_db
from app.api.openapi_responses import PREFERENCES_UPDATE_RESPONSES
from app.schemas.auth import CurrentUserResponse
from app.schemas.preferences import (
    PreferencesUpdateRequest,
    PreferencesUpdateResponse,
)
from app.services import auth as auth_service
from app.services import preferences as preferences_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=CurrentUserResponse)
async def read_me(current_user: ActiveUser) -> CurrentUserResponse:
    """Return the authenticated user's profile.

    Args:
        current_user: Authenticated user (password-change gate applies;
            ``/me`` is exempt).

    Returns:
        ``CurrentUserResponse`` for the current user.

    Raises:
        AuthRequired: 401 if unauthenticated.
        HTTPException: 403 if password change is required on a non-exempt path.
    """
    return await auth_service.get_current_user_profile(current_user)


@router.patch(
    "/me/preferences",
    response_model=PreferencesUpdateResponse,
    responses=PREFERENCES_UPDATE_RESPONSES,
)
async def update_preferences(
    payload: PreferencesUpdateRequest,
    current_user: ActiveUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreferencesUpdateResponse:
    """Update the authenticated user's preferred UI language.

    Exempt from the must-change-password gate so users can switch language
    before completing forced password change.

    Only canonical ``zh-TW`` / ``en`` / ``es`` are accepted (dropdown values);
    anything else returns 400 ``Invalid language code``.
    """
    return await preferences_service.update_preferences(db, current_user, payload)
