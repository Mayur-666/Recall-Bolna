"""Starting and closing real Bolna calls for a signed-in user."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError, UpstreamError
from app.integrations.bolna_client import BolnaClient, BolnaError
from app.models import CallSession, User
from app.repositories.call_sessions import CallSessionsRepo
from app.repositories.tool_calls import ToolCallsRepo
from app.services.call_sessions import CallSessionService, build_user_data, redacted_user_data
from app.services.events import get_event_bus

TERMINAL = {"completed", "call-disconnected", "failed", "error", "no-answer", "busy", "canceled", "stopped"}
NO_EXECUTION_NOTE = (
    "Bolna didn't report an execution id for this call (it is linked on the first memory search), "
    "so the transcript can't be fetched."
)


def _require_bolna() -> str:
    s = get_settings()
    missing = [k for k in ("BOLNA_API_KEY", "BOLNA_AGENT_ID") if not getattr(s, k)]
    if missing:
        raise ServiceUnavailableError(
            f"Voice calls need {', '.join(missing)} in the server environment (.env)."
        )
    return s.BOLNA_AGENT_ID


class CallsService:
    def __init__(self, session: AsyncSession, bolna: BolnaClient | None = None) -> None:
        self.session = session
        self.bolna = bolna or BolnaClient()
        self.sessions = CallSessionService(session)
        self.repo = CallSessionsRepo(session)

    async def _prepare(self, user: User, channel: str) -> tuple[CallSession, dict[str, Any]]:
        cs, token = await self.sessions.create(user.id, channel)
        user_data = await build_user_data(self.session, user, token)
        cs.user_data_sent = redacted_user_data(user_data)
        await self.session.commit()
        return cs, user_data

    async def _fail(self, cs: CallSession, exc: BolnaError) -> UpstreamError:
        cs.status = "failed"
        cs.revoked_at = datetime.now(UTC)
        await self.session.commit()
        return UpstreamError(
            "Bolna rejected the call request.",
            bolna_status=exc.status,
            bolna_body=exc.body_excerpt or str(exc),
        )

    async def start_web(self, user: User) -> tuple[CallSession, dict[str, Any]]:
        agent_id = _require_bolna()
        cs, user_data = await self._prepare(user, "web")
        try:
            session = await self.bolna.mint_web_session(agent_id, user_data)
        except BolnaError as exc:
            raise await self._fail(cs, exc) from exc
        cs.status = "minted"
        await self.session.commit()
        get_event_bus().publish(cs.id, {"type": "call_session_created", "channel": "web"})
        return cs, session

    async def start_phone(self, user: User, phone: str) -> tuple[CallSession, str]:
        agent_id = _require_bolna()
        cs, user_data = await self._prepare(user, "phone")
        try:
            execution_id = await self.bolna.make_call(agent_id, phone, user_data)
        except BolnaError as exc:
            raise await self._fail(cs, exc) from exc
        cs.bolna_execution_id = execution_id
        cs.status = "queued"
        await self.session.commit()
        get_event_bus().publish(cs.id, {"type": "call_session_created", "channel": "phone"})
        return cs, execution_id

    async def get(self, user: User, call_session_id: uuid.UUID) -> CallSession:
        cs = await self.repo.get(user.id, call_session_id)
        if cs is None:
            raise NotFoundError("Call not found.")
        return cs

    async def refresh(self, user: User, call_session_id: uuid.UUID) -> tuple[CallSession, str | None]:
        """Pull the latest status/transcript from Bolna's execution API (when an execution id is known)."""
        cs = await self.get(user, call_session_id)
        if not cs.bolna_execution_id:
            return cs, NO_EXECUTION_NOTE
        if cs.transcript:
            return cs, None
        try:
            execution = await self.bolna.get_execution(cs.bolna_execution_id)
        except BolnaError as exc:
            return cs, f"Could not fetch the execution from Bolna ({exc.status})."
        await self.apply_execution(cs, execution)
        return cs, None if cs.transcript else "Bolna hasn't published a transcript for this call yet."

    async def apply_execution(self, cs: CallSession, execution: dict[str, Any]) -> None:
        status = str(execution.get("status") or cs.status)
        cs.status = status
        transcript = execution.get("transcript")
        bus = get_event_bus()
        if isinstance(transcript, str) and transcript.strip() and not cs.transcript:
            cs.transcript = transcript
            cs.transcript_fetched_at = datetime.now(UTC)
            bus.publish(cs.id, {"type": "transcript_available"})
        if status in TERMINAL:
            cs.ended_at = cs.ended_at or datetime.now(UTC)
            cs.revoked_at = cs.revoked_at or datetime.now(UTC)
            bus.publish(cs.id, {"type": "call_ended", "status": status})
        await self.session.commit()

    async def end(self, user: User, call_session_id: uuid.UUID) -> tuple[CallSession, str | None]:
        """Called by the browser on the SDK call-end event: revoke the token, then fetch the transcript."""
        cs = await self.get(user, call_session_id)
        cs.revoked_at = cs.revoked_at or datetime.now(UTC)
        cs.ended_at = cs.ended_at or datetime.now(UTC)
        if cs.status in ("created", "minted", "queued"):
            cs.status = "ended"
        await self.session.commit()
        get_event_bus().publish(cs.id, {"type": "call_ended", "status": cs.status})
        return await self.refresh(user, call_session_id)


async def history_events(session: AsyncSession, cs: CallSession) -> list[dict[str, Any]]:
    """Persisted events for a call, so a reloaded page rebuilds the same live view."""
    events: list[dict[str, Any]] = [{"type": "call_session_created", "channel": cs.channel}]
    for call in await ToolCallsRepo(session).list_for_session(cs.user_id, cs.id):
        events.append(
            {
                "type": "tool_call_started",
                "tool_call_id": str(call.id),
                "tool": call.tool_name,
                "question": call.original_question,
                "standalone_query": call.standalone_query,
            }
        )
        if call.result_status in ("started",):
            continue
        if call.result_status in ("error", "not_found"):
            events.append({"type": "tool_call_failed", "tool_call_id": str(call.id), "tool": call.tool_name})
            continue
        done: dict[str, Any] = {
            "type": "tool_call_completed",
            "tool_call_id": str(call.id),
            "tool": call.tool_name,
            "status": call.result_status,
            "timings_ms": call.timings_ms,
        }
        if call.tool_name == "search_memories":
            done["results"] = (call.result or {}).get("results", [])
        else:
            done["context"] = call.result
        events.append(done)
    if cs.ended_at is not None:
        events.append({"type": "call_ended", "status": cs.status})
    if cs.transcript:
        events.append({"type": "transcript_available"})
    return events
