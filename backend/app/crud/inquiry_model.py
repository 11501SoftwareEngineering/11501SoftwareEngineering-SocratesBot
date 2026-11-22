"""Read the inquiry model catalog."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.gemini import GEMINI_MODEL
from app.models.inquiry_model import InquiryModel


async def list_inquiry_models(db: AsyncSession) -> list[InquiryModel]:
    result = await db.scalars(
        select(InquiryModel)
        .where(InquiryModel.model_id == GEMINI_MODEL)
        .order_by(InquiryModel.sort_order)
    )
    return list(result)


async def get_inquiry_model(db: AsyncSession, model_id: str) -> InquiryModel | None:
    if model_id != GEMINI_MODEL:
        return None
    return await db.get(InquiryModel, model_id)
