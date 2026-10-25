import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models import CallSession, User
from app.repositories.call_sessions import CallSessionsRepo
from app.repositories.tool_calls import ToolCallsRepo
from app.schemas.call import (
    CallSessionDetail,
    CallSessionOut,
    PhoneCallOut,
    PhoneCallRequest,
    ToolCallOut,
    WebSessionOut,
)
from app.services.calls import CallsService, history_events
from app.services.events import get_event_bus

router = APIRouter(prefix="/calls", tags=["calls"])


def _out(cs: CallSession, note: str | None = None) -> CallSessionOut:
    return CallSessionOut.model_validate(cs).model_copy(update={"transcript_note": note})


@router.post("/web-session", response_model=WebSessionOut)
async def web_session(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> WebSessionOut:
    cs, session = await CallsService(db).start_web(user)
    return WebSessionOut(call_session_id=cs.id, session=session)


@router.post("/phone", response_model=PhoneCallOut)
async def phone_call(
    body: PhoneCallRequest, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> PhoneCallOut:
    cs, execution_id = await CallsService(db).start_phone(user, body.phone)
    return PhoneCallOut(call_session_id=cs.id, execution_id=execution_id)


@router.get("", response_model=list[CallSessionOut])
async def list_calls(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[CallSessionOut]:
    return [_out(cs) for cs in await CallSessionsRepo(db).list_for_user(user.id)]


@router.get("/{call_session_id}", response_model=CallSessionDetail)
async def get_call(
    call_session_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> CallSessionDetail:
    cs, note = await CallsService(db).refresh(user, call_session_id)
    calls = await ToolCallsRepo(db).list_for_session(user.id, cs.id)
    return CallSessionDetail(
        **_out(cs, note).model_dump(), tool_calls=[ToolCallOut.model_validate(c) for c in calls]
    )


@router.post("/{call_session_id}/end", response_model=CallSessionOut)
async def end_call(
    call_session_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> CallSessionOut:
    cs, note = await CallsService(db).end(user, call_session_id)
    return _out(cs, note)


KEEPALIVE_S = 15.0


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@router.get("/{call_session_id}/events")
async def call_events(
    call_session_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """Server-sent events: persisted history first, then live backend-observed events."""
    cs = await CallsService(db).get(user, call_session_id)
    bus = get_event_bus()
    queue = bus.register(cs.id)  # registered before reading history so nothing is missed
    history = await history_events(db, cs)

    async def stream() -> AsyncIterator[str]:
        try:
            for event in history:
                yield _sse(event)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
                    yield _sse(event)
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            bus.unregister(cs.id, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
