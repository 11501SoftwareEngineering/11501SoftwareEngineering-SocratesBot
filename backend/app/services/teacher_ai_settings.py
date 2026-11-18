"""Read and update a teacher's provider key and default model."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import teacher_ai_settings as settings_crud
from app.models.inquiry_model import InquiryModel
from app.models.teacher_ai_settings import TeacherAiSettings
from app.models.user import User
from app.schemas.teacher_ai_settings import (
    AiSettingsResponse,
    ApiKeyRequest,
    ApiKeyResponse,
    DefaultModelRequest,
    DefaultModelResponse,
    DefaultModelUpdateResponse,
)

_MIN_MASKED = 20


def mask_api_key(api_key: str) -> str:
    """Return the first 3 characters, three dots, and the last 4."""
    if len(api_key) < _MIN_MASKED:
        return "..."
    return f"{api_key[:3]}...{api_key[-4:]}"


def _default_model(model: InquiryModel | None) -> DefaultModelResponse | None:
    if model is None:
        return None
    return DefaultModelResponse(id=model.model_id, name=model.name)


async def _loaded_default(
    db: AsyncSession, row: TeacherAiSettings | None
) -> DefaultModelResponse | None:
    if row is None or row.default_model_id is None:
        return None
    model = await settings_crud.get_inquiry_model(db, row.default_model_id)
    return _default_model(model)


async def read_settings(db: AsyncSession, current_user: User) -> AiSettingsResponse:
    row = await settings_crud.get_settings(db, current_user.id)
    api_key = None if row is None else row.api_key
    return AiSettingsResponse(
        configured=api_key is not None,
        masked_key=None if api_key is None else mask_api_key(api_key),
        updated_at=None if row is None else row.key_updated_at,
        default_model=await _loaded_default(db, row),
    )


async def save_api_key(
    db: AsyncSession, current_user: User, payload: ApiKeyRequest
) -> ApiKeyResponse:
    row = await settings_crud.save_api_key(db, current_user.id, payload.api_key)
    if row.api_key is None or row.key_updated_at is None:
        raise RuntimeError("failed to store teacher ai settings")
    return ApiKeyResponse(
        configured=True,
        masked_key=mask_api_key(row.api_key),
        updated_at=row.key_updated_at,
    )


async def clear_api_key(db: AsyncSession, current_user: User) -> None:
    await settings_crud.clear_api_key(db, current_user.id)


async def set_default_model(
    db: AsyncSession, current_user: User, payload: DefaultModelRequest
) -> DefaultModelUpdateResponse:
    model = await settings_crud.get_inquiry_model(db, payload.model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown model",
        )
    await settings_crud.set_default_model(db, current_user.id, model.model_id)
    return DefaultModelUpdateResponse(
        default_model=DefaultModelResponse(id=model.model_id, name=model.name),
        message="Default model updated",
    )
