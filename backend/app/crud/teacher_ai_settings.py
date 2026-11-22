"""Persist one teacher_ai_settings row per teacher."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inquiry_model import InquiryModel
from app.models.teacher_ai_settings import TeacherAiSettings

_STORE_FAILED = "failed to store teacher ai settings"


async def get_settings(
    db: AsyncSession, user_id: uuid.UUID
) -> TeacherAiSettings | None:
    return await db.get(TeacherAiSettings, user_id)


async def get_inquiry_model(db: AsyncSession, model_id: str) -> InquiryModel | None:
    """Return the catalog row for ``model_id``, or None when it is absent."""
    return await db.get(InquiryModel, model_id)


async def save_api_key(
    db: AsyncSession, user_id: uuid.UUID, api_key_ciphertext: str, masked_key: str
) -> TeacherAiSettings:
    """Store the ciphertext and mask. A second save replaces both on the same row."""
    now = datetime.now(UTC)
    stmt = (
        insert(TeacherAiSettings)
        .values(
            user_id=user_id,
            api_key_ciphertext=api_key_ciphertext,
            masked_key=masked_key,
            key_updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[TeacherAiSettings.user_id],
            set_={
                "api_key_ciphertext": api_key_ciphertext,
                "masked_key": masked_key,
                "key_updated_at": now,
            },
        )
    )
    try:
        await db.execute(stmt)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError(_STORE_FAILED) from None
    row = await get_settings(db, user_id)
    if row is not None:
        await db.refresh(row)
    if row is None or row.api_key_ciphertext is None or row.masked_key is None:
        raise RuntimeError(_STORE_FAILED)
    return row


async def clear_api_key(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Remove the ciphertext and mask. Leave the default model and the row otherwise."""
    await db.execute(
        update(TeacherAiSettings)
        .where(TeacherAiSettings.user_id == user_id)
        .values(api_key_ciphertext=None, masked_key=None)
    )
    await db.commit()


async def set_default_model(
    db: AsyncSession, user_id: uuid.UUID, model_id: str
) -> None:
    """Set the default model. A second call replaces the previous id."""
    stmt = (
        insert(TeacherAiSettings)
        .values(user_id=user_id, default_model_id=model_id)
        .on_conflict_do_update(
            index_elements=[TeacherAiSettings.user_id],
            set_={"default_model_id": model_id},
        )
    )
    await db.execute(stmt)
    await db.commit()
