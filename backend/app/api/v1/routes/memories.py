import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models import User
from app.services.events import get_memory_bus
from app.services.memory_graph import memory_graph
from app.services.overview import list_memories, overview

router = APIRouter(tags=["memories"])


@router.get("/overview")
async def get_overview(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await overview(db, user.id)


@router.get("/memories/graph")
async def get_memory_graph(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await memory_graph(db, user.id)


KEEPALIVE_S = 15.0


@router.get("/memories/events")
async def memory_events(user: User = Depends(current_user)) -> StreamingResponse:
    """Server-sent events for this user's memories: a conversation started processing, finished
    (with the memories it produced) or failed. Lets the dashboard show new memories the moment they form."""
    bus = get_memory_bus()
    queue = bus.register(user.id)

    async def stream() -> AsyncIterator[str]:
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            bus.unregister(user.id, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/memories")
async def get_memories(
    kind: str | None = Query(None, pattern="^(decision|commitment|action_item|fact|date|person)$"),
    state: str | None = Query(None, pattern="^(proposed|decided|superseded|rejected|unresolved)$"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await list_memories(db, user.id, kind, state)
