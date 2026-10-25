import uuid
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Computed, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base, CreatedAtMixin, IdMixin

_DIM = get_settings().EMBED_DIM


class MemoryItem(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "memory_items"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # decision|commitment|action_item|fact|date|person
    topic: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    speaker: Mapped[str | None] = mapped_column(String(120))
    owner: Mapped[str | None] = mapped_column(String(120))
    owner_is_user: Mapped[bool] = mapped_column(Boolean, default=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    decision_state: Mapped[str | None] = mapped_column(String(12))
    change_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_items.id", ondelete="SET NULL")
    )
    # Set by the decision linker when a later decision explicitly contradicts an earlier one
    # without replacing it (both stay "decided"; answers must present both).
    conflict_with_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_items.id", ondelete="SET NULL")
    )
    evidence_quote: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="SET NULL")
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(_DIM))
    topic_embedding: Mapped[list[float]] = mapped_column(Vector(_DIM))
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', topic || ' ' || statement || ' ' || evidence_quote)", persisted=True
        ),
    )
