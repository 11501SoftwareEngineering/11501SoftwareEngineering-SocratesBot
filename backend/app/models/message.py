import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DialogueMessage(Base):
    """One visible turn. The row never stores the provider key or a student name."""

    __tablename__ = "dialogue_messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "request_id",
            name="uq_dialogue_messages_session_id_request_id",
        ),
        CheckConstraint(
            "sender IN ('ai', 'student')",
            name="sender",
        ),
        CheckConstraint(
            "generation_meta IS NULL OR jsonb_typeof(generation_meta) = 'object'",
            name="generation_meta_object",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generation_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
