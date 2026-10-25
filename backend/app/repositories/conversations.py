import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation


class ConversationsRepo:
    """Every read and write is scoped to a user; there is no unscoped lookup."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )

    async def get_by_hash(self, user_id: uuid.UUID, content_hash: str) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation).where(
                Conversation.user_id == user_id, Conversation.content_hash == content_hash
            )
        )

    async def list_for_user(
        self, user_id: uuid.UUID, q: str | None = None, status: str | None = None
    ) -> Sequence[Conversation]:
        stmt = select(Conversation).where(Conversation.user_id == user_id)
        if status:
            stmt = stmt.where(Conversation.status == status)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Conversation.title.ilike(like), Conversation.transcript_text.ilike(like)))
        stmt = stmt.order_by(Conversation.conversation_date.desc(), Conversation.created_at.desc())
        return (await self.session.scalars(stmt)).all()

    async def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def delete(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )

    async def titles_by_status(self, user_id: uuid.UUID, statuses: tuple[str, ...]) -> dict[str, list[str]]:
        rows = await self.session.execute(
            select(Conversation.status, Conversation.title).where(
                Conversation.user_id == user_id, Conversation.status.in_(statuses)
            )
        )
        out: dict[str, list[str]] = {s: [] for s in statuses}
        for status, title in rows:
            out[status].append(title)
        return out

    async def count_ready(self, user_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.user_id == user_id, Conversation.status == "ready")
            )
            or 0
        )
