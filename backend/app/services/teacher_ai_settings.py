"""Read and update a teacher's provider key and default model."""

import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.gemini import GEMINI_MODEL
from app.core.security import decrypt_api_key, encrypt_api_key
from app.crud import course as course_crud
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
from app.services.ai_usage import AttributedKey

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
    model_id = GEMINI_MODEL
    model = await settings_crud.get_inquiry_model(db, model_id)
    return _default_model(model)


async def read_settings(db: AsyncSession, current_user: User) -> AiSettingsResponse:
    row = await settings_crud.get_settings(db, current_user.id)
    stored = row is not None and row.api_key_ciphertext is not None
    return AiSettingsResponse(
        configured=stored,
        masked_key=row.masked_key if stored and row is not None else None,
        updated_at=None if row is None else row.key_updated_at,
        default_model=await _loaded_default(db, row),
    )


async def save_api_key(
    db: AsyncSession, current_user: User, payload: ApiKeyRequest
) -> ApiKeyResponse:
    keys = payload.api_keys if payload.api_keys is not None else [payload.api_key]
    stored = keys[0] if len(keys) == 1 else json.dumps({"version": 1, "keys": keys})
    mask = mask_api_key(keys[0]) + (f" x{len(keys)}" if len(keys) > 1 else "")
    row = await settings_crud.save_api_key(
        db,
        current_user.id,
        encrypt_api_key(stored),
        mask,
    )
    if (
        row.api_key_ciphertext is None
        or row.masked_key is None
        or row.key_updated_at is None
    ):
        raise RuntimeError("failed to store teacher ai settings")
    return ApiKeyResponse(
        configured=True,
        masked_key=row.masked_key,
        updated_at=row.key_updated_at,
    )


async def openrouter_api_key(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Return the teacher key or server-attributed credential (pool resolves at dispatch)."""
    row = await settings_crud.get_settings(db, user_id)
    stored = None if row is None else row.api_key_ciphertext
    if not isinstance(stored, str) or stored == "":
        return AttributedKey(
            settings.OPENAI_API_KEY.get_secret_value(), user_id, "server"
        )
    try:
        value = decrypt_api_key(stored)
        keys = [value]
        if value.startswith("{"):
            bundle = json.loads(value)
            if bundle.get("version") != 1:
                raise ValueError("Unsupported credential bundle")
            keys = ApiKeyRequest(api_keys=bundle["keys"]).api_keys
        credential = AttributedKey(keys[0], user_id, "teacher")
        credential.api_keys = tuple(keys)
        credential.gemini_only = True
        return credential
    except (RuntimeError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Teacher API key cannot be read",
        ) from None


async def clear_api_key(db: AsyncSession, current_user: User) -> None:
    await settings_crud.clear_api_key(db, current_user.id)


async def set_default_model(
    db: AsyncSession, current_user: User, payload: DefaultModelRequest
) -> DefaultModelUpdateResponse:
    if payload.model_id != GEMINI_MODEL:
        raise HTTPException(422, "Unknown model")
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


async def effective_default_model(db: AsyncSession, teacher_id: uuid.UUID) -> str:
    """Offer the sole Gemini default while keeping historical settings stored."""
    row = await settings_crud.get_settings(db, teacher_id)
    if (
        row is not None
        and row.default_model_id == GEMINI_MODEL
        and await settings_crud.get_inquiry_model(db, GEMINI_MODEL) is None
    ):
        raise HTTPException(422, "Saved default model is unavailable")
    return GEMINI_MODEL


async def course_api_key(db: AsyncSession, course_id: uuid.UUID) -> str:
    """Resolve the course owner's key, never the caller's billing identity."""
    course = await course_crud.get_course_by_id(db, course_id)
    if course is None:
        raise HTTPException(status_code=503, detail="AI course is unavailable")
    return await openrouter_api_key(db, course.created_by)
