from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, TeacherUser, get_db
from app.api.openapi_responses import PREFERENCES_UPDATE_RESPONSES
from app.schemas.ai_usage import AiUsageResponse
from app.schemas.auth import CurrentUserResponse
from app.schemas.preferences import (
    PreferencesUpdateRequest,
    PreferencesUpdateResponse,
)
from app.schemas.teacher_ai_settings import (
    AiSettingsResponse,
    ApiKeyRequest,
    ApiKeyResponse,
    DefaultModelRequest,
    DefaultModelUpdateResponse,
)
from app.services import ai_usage as ai_usage_service
from app.services import auth as auth_service
from app.services import preferences as preferences_service
from app.services import teacher_ai_settings as teacher_ai_settings_service

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


@router.get("/me/ai/settings", response_model=AiSettingsResponse)
async def read_ai_settings(
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiSettingsResponse:
    """Return the teacher's key status and default model. The raw key stays stored."""
    return await teacher_ai_settings_service.read_settings(db, current_user)


@router.put("/me/ai/api-key", response_model=ApiKeyResponse)
async def save_ai_api_key(
    payload: ApiKeyRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyResponse:
    """Store the teacher's provider key and return only its mask."""
    return await teacher_ai_settings_service.save_api_key(db, current_user, payload)


@router.delete("/me/ai/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_api_key(
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove the stored key. The default model stays. Missing key is still 204."""
    await teacher_ai_settings_service.clear_api_key(db, current_user)


@router.patch("/me/ai/model", response_model=DefaultModelUpdateResponse)
async def update_default_model(
    payload: DefaultModelRequest,
    current_user: TeacherUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DefaultModelUpdateResponse:
    """Set the default model for new topics. Existing topics stay unchanged."""
    return await teacher_ai_settings_service.set_default_model(
        db, current_user, payload
    )


@router.get("/me/ai/usage", response_model=AiUsageResponse)
async def read_ai_usage(
    current_user: TeacherUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> AiUsageResponse:
    """Aggregate the course owner's actual outbound requests for the current UTC month.

    Includes retries and failed/invalid completions. Unknown usage/cost is null.
    No historical provider-account imports or unrelated-account usage is included.
    """
    return await ai_usage_service.read_month(db, current_user.id)
