import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolCall


class ToolCallsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, call: ToolCall) -> ToolCall:
        self.session.add(call)
        await self.session.flush()
        return call

    async def count_since(self, call_session_id: uuid.UUID, seconds: int) -> int:
        since = datetime.now(UTC) - timedelta(seconds=seconds)
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(ToolCall)
                .where(ToolCall.call_session_id == call_session_id, ToolCall.created_at >= since)
            )
            or 0
        )

    async def list_for_session(self, user_id: uuid.UUID, call_session_id: uuid.UUID) -> Sequence[ToolCall]:
        return (
            await self.session.scalars(
                select(ToolCall)
                .where(ToolCall.user_id == user_id, ToolCall.call_session_id == call_session_id)
                .order_by(ToolCall.created_at)
            )
        ).all()
