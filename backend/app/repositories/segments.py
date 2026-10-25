import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TranscriptSegment


class SegmentsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_conversation(
        self, user_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Sequence[TranscriptSegment]:
        return (
            await self.session.scalars(
                select(TranscriptSegment)
                .where(
                    TranscriptSegment.user_id == user_id,
                    TranscriptSegment.conversation_id == conversation_id,
                )
                .order_by(TranscriptSegment.seq)
            )
        ).all()
