import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class CallSession(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "call_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(8))  # web | phone
    # Only the SHA-256 of the per-call token is stored; the raw token goes to Bolna once.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bolna_execution_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # run_id returned by the web-call session mint (SDK v3); may equal the execution id (unverified).
    bolna_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="created")
    user_data_sent: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
