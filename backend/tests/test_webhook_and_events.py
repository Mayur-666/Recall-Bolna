import asyncio
import json
import uuid

import pytest

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import CallSession, ToolCall
from app.services.call_sessions import CallSessionService
from app.services.events import get_event_bus

WEBHOOK = "/api/v1/bolna/webhook"
BOLNA_IP = {"X-Forwarded-For": "13.203.39.153"}


async def session_with_execution(user, execution_id):
    async with get_sessionmaker()() as s:
        cs, _ = await CallSessionService(s).create(user.id, "web")
        cs.bolna_execution_id = execution_id
        await s.commit()
    return cs


@pytest.fixture(autouse=True)
def trust_proxy(monkeypatch):
    monkeypatch.setattr(get_settings(), "BOLNA_WEBHOOK_IP", "13.203.39.153")


async def test_webhook_wrong_ip_403(client, make_user):
    user, _ = await make_user()
    exe = uuid.uuid4().hex
    await session_with_execution(user, exe)
    resp = await client.post(
        WEBHOOK, json={"id": exe, "status": "completed"}, headers={"X-Forwarded-For": "1.2.3.4"}
    )
    assert resp.status_code == 403


async def test_webhook_unknown_execution_ignored_202(client):
    resp = await client.post(WEBHOOK, json={"id": "nobody-knows", "status": "completed"}, headers=BOLNA_IP)
    assert resp.status_code == 202


async def test_webhook_terminal_status_stores_transcript_and_revokes(client, make_user):
    user, _ = await make_user()
    exe = uuid.uuid4().hex
    cs = await session_with_execution(user, exe)
    resp = await client.post(
        WEBHOOK,
        json={"id": exe, "status": "completed", "transcript": "user: hi\nassistant: hello"},
        headers=BOLNA_IP,
    )
    assert resp.status_code == 200
    async with get_sessionmaker()() as s:
        row = await s.get(CallSession, cs.id)
    assert row.status == "completed"
    assert row.transcript == "user: hi\nassistant: hello"
    assert row.revoked_at is not None and row.ended_at is not None


async def test_webhook_in_progress_does_not_revoke(client, make_user):
    user, _ = await make_user()
    exe = uuid.uuid4().hex
    cs = await session_with_execution(user, exe)
    await client.post(WEBHOOK, json={"id": exe, "status": "in-progress"}, headers=BOLNA_IP)
    async with get_sessionmaker()() as s:
        row = await s.get(CallSession, cs.id)
    assert row.status == "in-progress" and row.revoked_at is None


async def test_webhook_duplicate_delivery_idempotent(client, make_user):
    user, _ = await make_user()
    exe = uuid.uuid4().hex
    cs = await session_with_execution(user, exe)
    payload = {"id": exe, "status": "completed", "transcript": "first"}
    await client.post(WEBHOOK, json=payload, headers=BOLNA_IP)
    await client.post(WEBHOOK, json={**payload, "transcript": "second"}, headers=BOLNA_IP)
    async with get_sessionmaker()() as s:
        row = await s.get(CallSession, cs.id)
    assert row.transcript == "first"


async def _read_sse(body_iterator, n):
    events = []
    async for chunk in body_iterator:
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        if len(events) >= n:
            break
    return events


async def test_sse_replays_history_then_live_event(make_user):
    # httpx's ASGI transport buffers whole responses, so the endpoint's stream is read directly.
    from app.api.v1.routes.calls import call_events

    user, _ = await make_user()
    async with get_sessionmaker()() as s:
        cs, _ = await CallSessionService(s).create(user.id, "web")
        s.add(
            ToolCall(
                call_session_id=cs.id, user_id=user.id, tool_name="search_memories", original_question="q?",
                standalone_query="q", result_status="found", result={"results": []}, timings_ms={"total": 12},
            )
        )  # fmt: skip
        await s.commit()

    async with get_sessionmaker()() as db:
        resp = await call_events(cs.id, user, db)
        assert resp.media_type == "text/event-stream"
        get_event_bus().publish(cs.id, {"type": "call_ended", "status": "completed"})
        events = await asyncio.wait_for(_read_sse(resp.body_iterator, 4), timeout=5)
        await resp.body_iterator.aclose()
    types = [e["type"] for e in events]
    assert types[:3] == ["call_session_created", "tool_call_started", "tool_call_completed"]
    assert events[2]["status"] == "found" and events[2]["timings_ms"] == {"total": 12}
    assert types[3] == "call_ended"


async def test_sse_other_user_404(client, make_user, login):
    a, _ = await make_user()
    async with get_sessionmaker()() as s:
        cs, _ = await CallSessionService(s).create(a.id, "web")
        await s.commit()
    b, pw = await make_user()
    await login(b, pw)
    resp = await client.get(f"/api/v1/calls/{cs.id}/events")
    assert resp.status_code == 404
