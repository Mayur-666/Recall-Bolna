import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, MemoryItem, TranscriptSegment


class ChunksRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_all(self, chunks: Sequence[Chunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()

    async def list_for_conversation(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Sequence[Chunk]:
        return (
            await self.session.scalars(
                select(Chunk)
                .where(Chunk.user_id == user_id, Chunk.conversation_id == conversation_id)
                .order_by(Chunk.seq)
            )
        ).all()


async def clear_derived(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
    """Remove everything ingestion produced for a conversation so it can be rebuilt."""
    for model in (MemoryItem, Chunk, TranscriptSegment):
        await session.execute(
            delete(model).where(model.user_id == user_id, model.conversation_id == conversation_id)
        )
