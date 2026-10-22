"""Preference update service."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locales import parse_preference_language
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.preferences import (
    PreferencesUpdateRequest,
    PreferencesUpdateResponse,
)

INVALID_LANGUAGE_DETAIL = "Invalid language code"


async def update_preferences(
    db: AsyncSession,
    current_user: User,
    payload: PreferencesUpdateRequest,
) -> PreferencesUpdateResponse:
    """Validate language and persist the user's sole preferred language."""
    try:
        code = parse_preference_language(payload.preferred_language)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_LANGUAGE_DETAIL,
        ) from exc
    updated = await user_crud.update_preferred_language(db, current_user, code=code)
    return PreferencesUpdateResponse(
        preferred_language=user_crud.preferred_language_code(updated),
        message="Preferences updated",
    )
