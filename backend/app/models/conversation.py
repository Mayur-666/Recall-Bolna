import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class Conversation(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_conversations_user_hash"),
        Index("ix_conversations_user_date", "user_id", "conversation_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    # When the conversation happened. Date questions use this, never created_at.
    conversation_date: Mapped[date] = mapped_column(Date)
    participants: Mapped[list[str]] = mapped_column(ARRAY(String(120)), default=list)
    self_speaker: Mapped[str | None] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(10))  # paste | upload
    original_filename: Mapped[str | None] = mapped_column(String(255))
    transcript_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
