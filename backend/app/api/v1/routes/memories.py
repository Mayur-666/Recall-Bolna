from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models import User
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


@router.get("/memories")
async def get_memories(
    kind: str | None = Query(None, pattern="^(decision|commitment|action_item|fact|date|person)$"),
    state: str | None = Query(None, pattern="^(proposed|decided|superseded|rejected|unresolved)$"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await list_memories(db, user.id, kind, state)
