import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryItem


class MemoryItemsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Sequence[MemoryItem]:
        return (
            await self.session.scalars(
                select(MemoryItem)
                .where(MemoryItem.user_id == user_id, MemoryItem.conversation_id == conversation_id)
                .order_by(MemoryItem.char_start)
            )
        ).all()
