from decimal import Decimal

from sqlalchemy import Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InquiryModel(Base):
    """OpenRouter model a teacher can pick; prices are USD per million tokens."""

    __tablename__ = "inquiry_models"

    model_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    input_price_usd: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    output_price_usd: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
