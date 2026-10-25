import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CallSession


class CallSessionsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, cs: CallSession) -> CallSession:
        self.session.add(cs)
        await self.session.flush()
        return cs

    async def get_by_token_hash(self, token_hash: str) -> CallSession | None:
        return await self.session.scalar(select(CallSession).where(CallSession.token_hash == token_hash))

    async def get(self, user_id: uuid.UUID, session_id: uuid.UUID) -> CallSession | None:
        return await self.session.scalar(
            select(CallSession).where(CallSession.id == session_id, CallSession.user_id == user_id)
        )

    async def get_by_execution(self, execution_id: str) -> CallSession | None:
        return await self.session.scalar(
            select(CallSession).where(
                (CallSession.bolna_execution_id == execution_id) | (CallSession.bolna_run_id == execution_id)
            )
        )

    async def list_for_user(self, user_id: uuid.UUID, limit: int = 50) -> Sequence[CallSession]:
        return (
            await self.session.scalars(
                select(CallSession)
                .where(CallSession.user_id == user_id)
                .order_by(CallSession.created_at.desc())
                .limit(limit)
            )
        ).all()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(CallSession)
            .where(CallSession.user_id == user_id, CallSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
