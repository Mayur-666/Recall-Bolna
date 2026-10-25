import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, MemoryItem
from app.services.retrieval import memory_counts


def memory_row(item: MemoryItem, conv: Conversation) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "conversation_id": str(conv.id),
        "conversation_title": conv.title,
        "conversation_date": conv.conversation_date.isoformat(),
        "kind": item.kind,
        "topic": item.topic,
        "statement": item.statement,
        "speaker": item.speaker,
        "owner": item.owner,
        "owner_is_user": item.owner_is_user,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "decision_state": item.decision_state,
        "superseded_by_id": str(item.superseded_by_id) if item.superseded_by_id else None,
        "conflict_with_id": str(item.conflict_with_id) if item.conflict_with_id else None,
        "evidence_quote": item.evidence_quote,
    }


async def list_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str | None = None,
    state: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = (
        select(MemoryItem, Conversation)
        .join(Conversation, Conversation.id == MemoryItem.conversation_id)
        .where(MemoryItem.user_id == user_id, Conversation.status == "ready")
    )
    if kind:
        stmt = stmt.where(MemoryItem.kind == kind)
    if state:
        stmt = stmt.where(MemoryItem.decision_state == state)
    stmt = stmt.order_by(Conversation.conversation_date.desc(), MemoryItem.char_start).limit(limit)
    return [memory_row(item, conv) for item, conv in (await session.execute(stmt)).all()]


async def overview(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    conversations, memories = await memory_counts(session, user_id)
    decisions = await list_memories(session, user_id, kind="decision", limit=5)
    actions = [
        m
        for m in await list_memories(session, user_id, limit=200)
        if m["kind"] in ("action_item", "commitment")
    ][:5]
    attention = (
        await session.scalars(
            select(Conversation)
            .where(
                Conversation.user_id == user_id, Conversation.status.in_(("queued", "processing", "failed"))
            )
            .order_by(Conversation.created_at.desc())
        )
    ).all()
    return {
        "conversation_count": conversations,
        "memory_count": memories,
        "recent_decisions": decisions,
        "open_action_items": actions,
        "needs_attention": [
            {"id": str(c.id), "title": c.title, "status": c.status, "error": c.error_message}
            for c in attention
        ],
    }
