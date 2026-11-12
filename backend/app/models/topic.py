import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import TopicStage


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('setup', 'conversation', 'summary')",
            name="stage",
        ),
        CheckConstraint(
            "age_band IS NULL OR age_band IN ('13-15', '16-18', 'university_plus')",
            name="age_band",
        ),
        CheckConstraint(
            "max_turns IS NULL OR max_turns IN (5, 10, 15)",
            name="max_turns",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TopicStage.SETUP.value,
        server_default=TopicStage.SETUP.value,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    content_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    age_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    max_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Course title stays on ``title``. This is the inquiry topic and may be empty in setup.
    inquiry_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    core_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    inquiry_focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    background_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclusions: Mapped[str | None] = mapped_column(Text, nullable=True)
    opening_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
