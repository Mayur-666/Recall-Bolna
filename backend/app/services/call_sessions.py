"""Per-call tokens that tie a Bolna call to exactly one Recall user.

The raw token leaves the server once (inside Bolna's user_data) and only its SHA-256
is stored. Every tool request re-validates it: unknown, expired or revoked -> 401.
The model never supplies identity.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthError
from app.core.security import hash_token, new_call_token
from app.models import CallSession, User
from app.repositories.call_sessions import CallSessionsRepo
from app.services.dates import today_local
from app.services.retrieval import memory_counts


class CallSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CallSessionsRepo(session)

    async def create(self, user_id: uuid.UUID, channel: str) -> tuple[CallSession, str]:
        raw = new_call_token()
        cs = CallSession(
            user_id=user_id,
            channel=channel,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().CALL_TOKEN_TTL_MIN),
            status="created",
            user_data_sent={},
        )
        await self.repo.add(cs)
        return cs, raw

    async def resolve(self, raw_token: str | None) -> CallSession:
        if not raw_token:
            raise AuthError("Missing call session.")
        cs = await self.repo.get_by_token_hash(hash_token(raw_token))
        if cs is None or cs.revoked_at is not None or cs.expires_at <= datetime.now(UTC):
            raise AuthError("Call session is invalid or has ended.")
        return cs

    async def revoke(self, session_id: uuid.UUID) -> None:
        cs = await self.session.get(CallSession, session_id)
        if cs is not None and cs.revoked_at is None:
            cs.revoked_at = datetime.now(UTC)

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.repo.revoke_all_for_user(user_id)

    async def link_execution(self, cs: CallSession, execution_id: str | None) -> None:
        # First value wins: a later, different id can't re-point the session.
        if execution_id and cs.bolna_execution_id is None:
            cs.bolna_execution_id = execution_id[:64]


async def build_user_data(session: AsyncSession, user: User, token: str) -> dict[str, Any]:
    """Variables for the agent prompt. Counts come from the database, never from the model."""
    conversations, memories = await memory_counts(session, user.id)
    return {
        "recall_session": token,
        "user_name": user.display_name,
        "conversation_count": conversations,
        "memory_count": memories,
        "today": today_local().isoformat(),
    }


def redacted_user_data(user_data: dict[str, Any]) -> dict[str, Any]:
    """What we persist about what was sent: never the raw token."""
    return {k: ("***" if k == "recall_session" else v) for k, v in user_data.items()}
