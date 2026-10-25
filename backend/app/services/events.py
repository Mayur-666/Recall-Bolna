"""In-process pub/sub for live call events (single backend process; see README limitations)."""

import asyncio
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

Queue = asyncio.Queue[dict[str, Any]]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[uuid.UUID, set[Queue]] = defaultdict(set)

    def publish(self, call_session_id: uuid.UUID, event: dict[str, Any]) -> None:
        for q in list(self._subs.get(call_session_id, ())):
            if not q.full():
                q.put_nowait(event)

    def register(self, call_session_id: uuid.UUID) -> Queue:
        q: Queue = asyncio.Queue(maxsize=200)
        self._subs[call_session_id].add(q)
        return q

    def unregister(self, call_session_id: uuid.UUID, q: Queue) -> None:
        self._subs[call_session_id].discard(q)
        if not self._subs[call_session_id]:
            self._subs.pop(call_session_id, None)

    async def subscribe(self, call_session_id: uuid.UUID) -> AsyncIterator[dict[str, Any]]:
        q = self.register(call_session_id)
        try:
            while True:
                yield await q.get()
        finally:
            self.unregister(call_session_id, q)


@lru_cache
def get_event_bus() -> EventBus:
    return EventBus()
