import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TeacherAiSettings(Base):
    """One teacher's provider key and default model for new topics."""

    __tablename__ = "teacher_ai_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    default_model_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("inquiry_models.model_id"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            "TeacherAiSettings("
            f"user_id={self.user_id!s}, "
            f"key_updated_at={self.key_updated_at!r}, "
            f"default_model_id={self.default_model_id!r})"
        )
