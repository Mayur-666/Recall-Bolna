import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class ToolCall(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "tool_calls"

    call_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(40))
    original_question: Mapped[str | None] = mapped_column(Text)
    standalone_query: Mapped[str | None] = mapped_column(Text)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # never holds the call token
    result_status: Mapped[str] = mapped_column(String(24), default="started")
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timings_ms: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
