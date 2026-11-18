"""Read the inquiry model catalog."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inquiry_model import InquiryModel


async def list_inquiry_models(db: AsyncSession) -> list[InquiryModel]:
    result = await db.scalars(select(InquiryModel).order_by(InquiryModel.sort_order))
    return list(result)
