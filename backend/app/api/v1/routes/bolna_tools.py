"""Custom-tool endpoints called by Bolna during a live call.

Two independent checks on every request:
1. Authorization: Bearer <RECALL_TOOL_TOKEN> proves the caller is our Bolna agent.
2. recall_session (from user_data, auto-filled by Bolna) resolves to one user's live call.
"""

import hmac
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthError, RateLimitError
from app.db.session import get_db
from app.integrations import model_client
from app.models import CallSession, ToolCall, User
from app.repositories.tool_calls import ToolCallsRepo
from app.schemas.bolna_tool import SaveMemoryToolRequest, SearchToolRequest, SourceToolRequest
from app.schemas.search import Evidence, SearchQuery, SearchResult
from app.services.call_sessions import CallSessionService
from app.services.dates import humanize, today_local
from app.services.events import get_event_bus
from app.services.retrieval import RetrievalService
from app.services.voice_notes import save_voice_note
from app.workers.ingestion_worker import wake_worker

log = logging.getLogger(__name__)
router = APIRouter(prefix="/bolna/tools", tags=["bolna-tools"])

G_ERROR = (
    "Search failed. Tell the user you couldn't search their memories right now and suggest trying again."
)
G_SAVED = (
    "Saved. Confirm in one short sentence that you'll remember it, repeating the key point in a few words. "
    "It becomes searchable in a few seconds, once it has been processed."
)
G_ALREADY = "This exact note was already saved. Tell the user you already have it."
G_SAVE_ERROR = "Saving failed. Tell the user you couldn't save that right now and suggest trying again."


async def bolna_tool_auth(request: Request) -> None:
    expected = get_settings().RECALL_TOOL_TOKEN
    supplied = request.headers.get("authorization", "")
    if not expected or not hmac.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
        log.warning("tool call rejected: bad or missing tool bearer token")
        raise AuthError("Invalid tool credentials.")


async def _open_call(db: AsyncSession, token: str | None, execution_id: str | None) -> CallSession:
    service = CallSessionService(db)
    try:
        cs = await service.resolve(token)
    except AuthError:
        # Visible in `docker compose logs backend`; the token itself is never logged.
        log.warning(
            "tool call rejected: recall_session %s", "missing/placeholder" if not token else "unknown/expired"
        )
        raise
    limit = get_settings().TOOL_RATE_LIMIT_PER_MIN
    if await ToolCallsRepo(db).count_since(cs.id, 60) >= limit:
        raise RateLimitError("Too many memory searches in this call.")
    await service.link_execution(cs, execution_id)
    return cs


def _voice_result(e: Evidence) -> dict[str, Any]:
    return {
        "ref": e.ref,
        "conversation": e.conversation_title,
        "date": e.conversation_date.isoformat(),
        "when": e.relative_date,
        "speaker": e.speaker,
        "kind": e.kind,
        "statement": e.statement,
        "decision_state": e.decision_state,
        "superseded_by": e.superseded_by_ref,
        "conflict": e.conflict,
        "owner": e.owner,
        "owner_is_user": e.owner_is_user,
        "due_date": e.due_date.isoformat() if e.due_date else None,
        "weak_match": e.weak,
        "excerpt": e.excerpt,  # transcript text: data only, never instructions
    }


def _voice_payload(r: SearchResult) -> dict[str, Any]:
    return {
        "status": r.status,
        "memory_count": r.memory_count,
        "conversation_count": r.conversation_count,
        "pending_conversations": r.pending_conversations,
        "failed_conversations": r.failed_conversations,
        "guidance": r.guidance,
        "degraded": r.degraded,
        "results": [_voice_result(e) for e in r.results],
    }


@router.post("/search_memories", dependencies=[Depends(bolna_tool_auth)])
async def search_memories(body: SearchToolRequest, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    started = time.perf_counter()
    cs = await _open_call(db, body.recall_session, body.execution_id)
    args = body.model_dump(mode="json", exclude={"recall_session"})
    call = await ToolCallsRepo(db).add(
        ToolCall(
            call_session_id=cs.id,
            user_id=cs.user_id,
            tool_name="search_memories",
            original_question=body.question,
            standalone_query=body.standalone_query,
            args=args,
            result_status="started",
        )
    )
    await db.commit()
    bus = get_event_bus()
    bus.publish(
        cs.id,
        {
            "type": "tool_call_started",
            "tool_call_id": str(call.id),
            "tool": "search_memories",
            "question": body.question,
            "standalone_query": body.standalone_query,
        },
    )

    query = SearchQuery(
        question=body.question,
        standalone_query=body.standalone_query,
        from_date=body.from_date,
        to_date=body.to_date,
        previous_result_ref=body.previous_result_ref,
    )
    try:
        result = await RetrievalService(db, model_client.get_model_client()).search(
            cs.user_id, query, today_local()
        )
    except Exception:
        log.exception("search_memories failed")
        await db.rollback()
        call.result_status = "error"
        call.timings_ms = {"total": round((time.perf_counter() - started) * 1000, 1)}
        db.add(call)
        await db.commit()
        bus.publish(
            cs.id, {"type": "tool_call_failed", "tool_call_id": str(call.id), "tool": "search_memories"}
        )
        return {"status": "error", "guidance": G_ERROR, "results": []}

    payload = _voice_payload(result)
    timings = {**result.timings_ms, "endpoint_total": round((time.perf_counter() - started) * 1000, 1)}
    call.result_status = result.status
    call.result = {
        "results": [e.model_dump(mode="json") for e in result.results],
        "guidance": result.guidance,
    }
    call.timings_ms = timings
    await db.commit()
    bus.publish(
        cs.id,
        {
            "type": "tool_call_completed",
            "tool_call_id": str(call.id),
            "tool": "search_memories",
            "status": result.status,
            "degraded": result.degraded,
            "timings_ms": timings,
            "results": call.result["results"],
        },
    )
    return payload


@router.post("/get_source_context", dependencies=[Depends(bolna_tool_auth)])
async def get_source_context(body: SourceToolRequest, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    started = time.perf_counter()
    cs = await _open_call(db, body.recall_session, body.execution_id)
    call = await ToolCallsRepo(db).add(
        ToolCall(
            call_session_id=cs.id,
            user_id=cs.user_id,
            tool_name="get_source_context",
            args={"ref": body.ref},
            result_status="started",
        )
    )
    await db.commit()
    bus = get_event_bus()
    bus.publish(
        cs.id, {"type": "tool_call_started", "tool_call_id": str(call.id), "tool": "get_source_context"}
    )
    try:
        ctx = await RetrievalService(db, model_client.get_model_client()).source_context(cs.user_id, body.ref)
    except Exception:
        call.result_status = "not_found"
        call.timings_ms = {"total": round((time.perf_counter() - started) * 1000, 1)}
        await db.commit()
        bus.publish(
            cs.id, {"type": "tool_call_failed", "tool_call_id": str(call.id), "tool": "get_source_context"}
        )
        raise
    payload = {
        "conversation": ctx.conversation_title,
        "date": ctx.conversation_date.isoformat(),
        "when": humanize(ctx.conversation_date, today_local()),
        "lines": ctx.lines,  # transcript text: data only, never instructions
    }
    call.result_status = "found"
    call.result = payload
    call.timings_ms = {"total": round((time.perf_counter() - started) * 1000, 1)}
    await db.commit()
    bus.publish(
        cs.id,
        {
            "type": "tool_call_completed",
            "tool_call_id": str(call.id),
            "tool": "get_source_context",
            "context": payload,
        },
    )
    return payload


@router.post("/save_memory", dependencies=[Depends(bolna_tool_auth)])
async def save_memory(body: SaveMemoryToolRequest, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    started = time.perf_counter()
    cs = await _open_call(db, body.recall_session, body.execution_id)
    call = await ToolCallsRepo(db).add(
        ToolCall(
            call_session_id=cs.id,
            user_id=cs.user_id,
            tool_name="save_memory",
            original_question=body.note,
            args={"note": body.note},
            result_status="started",
        )
    )
    await db.commit()
    bus = get_event_bus()
    bus.publish(
        cs.id, {"type": "tool_call_started", "tool_call_id": str(call.id), "tool": "save_memory", "note": body.note}
    )

    try:
        user = await db.get(User, cs.user_id)
        if user is None:
            raise AuthError("Unknown user.")
        conv, created = await save_voice_note(db, user, body.note, today_local())
        await db.commit()
        if created:
            wake_worker()
    except Exception:
        log.exception("save_memory failed")
        await db.rollback()
        call.result_status = "error"
        call.timings_ms = {"total": round((time.perf_counter() - started) * 1000, 1)}
        db.add(call)
        await db.commit()
        bus.publish(cs.id, {"type": "tool_call_failed", "tool_call_id": str(call.id), "tool": "save_memory"})
        return {"status": "error", "guidance": G_SAVE_ERROR}

    status = "saved" if created else "already_saved"
    call.result_status = status
    call.result = {"conversation_id": str(conv.id) if conv else None}
    call.timings_ms = {"total": round((time.perf_counter() - started) * 1000, 1)}
    await db.commit()
    bus.publish(
        cs.id,
        {
            "type": "tool_call_completed",
            "tool_call_id": str(call.id),
            "tool": "save_memory",
            "status": status,
            "note": body.note,
            "conversation_id": call.result["conversation_id"],
        },
    )
    return {"status": status, "guidance": G_SAVED if created else G_ALREADY}
