import json

import httpx
import pytest
import respx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import CallSession

BASE = "https://api.bolna.ai"


@pytest.fixture(autouse=True)
def bolna_env(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "BOLNA_API_KEY", "bn-test-key")
    monkeypatch.setattr(s, "BOLNA_AGENT_ID", "agent-123")
    monkeypatch.setattr(s, "BOLNA_WEB_CALL_SESSION_PATH", "/web-call/session")


@pytest.fixture
async def authed(client, make_user, login):
    user, pw = await make_user(name="Mayur")
    await login(user, pw)
    return user


@respx.mock
async def test_web_session_route_creates_call_session_and_hides_token_hash(client, authed):
    route = respx.post(f"{BASE}/web-call/session").mock(
        return_value=httpx.Response(200, json={"session": "s1"})
    )
    resp = await client.post("/api/v1/calls/web-session")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session"] == {"session": "s1"}
    assert "token_hash" not in json.dumps(body)
    sent = json.loads(route.calls[0].request.content)
    token = sent["user_data"]["recall_session"]
    assert token not in json.dumps(body)  # the browser never sees the call token
    async with get_sessionmaker()() as s:
        cs = await s.get(CallSession, body["call_session_id"])
    assert cs.user_id == authed.id and cs.channel == "web"
    assert cs.user_data_sent["recall_session"] == "***"


@respx.mock
async def test_user_data_counts_come_from_db(client, authed):
    route = respx.post(f"{BASE}/web-call/session").mock(return_value=httpx.Response(200, json={}))
    await client.post("/api/v1/calls/web-session")
    data = json.loads(route.calls[0].request.content)["user_data"]
    assert data["user_name"] == "Mayur"
    assert data["conversation_count"] == 0
    assert data["memory_count"] == 0


@respx.mock
async def test_mint_failure_returns_502_with_reason_and_revokes(client, authed):
    respx.post(f"{BASE}/web-call/session").mock(
        return_value=httpx.Response(404, json={"detail": "Not Found"})
    )
    resp = await client.post("/api/v1/calls/web-session")
    assert resp.status_code == 502
    err = resp.json()["error"]
    assert err["details"]["bolna_status"] == 404
    assert "Not Found" in err["details"]["bolna_body"]
    async with get_sessionmaker()() as s:
        rows = (await s.scalars(select(CallSession).where(CallSession.user_id == authed.id))).all()
    assert rows and all(r.revoked_at is not None and r.status == "failed" for r in rows)


async def test_web_session_requires_bolna_config(client, authed, monkeypatch):
    monkeypatch.setattr(get_settings(), "BOLNA_AGENT_ID", "")
    resp = await client.post("/api/v1/calls/web-session")
    assert resp.status_code == 503
    assert "BOLNA_AGENT_ID" in resp.json()["error"]["message"]


@pytest.mark.parametrize("phone", ["9876543210", "+0123", "+91 98765 43210", "abc"])
async def test_phone_route_validates_e164(client, authed, phone):
    resp = await client.post("/api/v1/calls/phone", json={"phone": phone})
    assert resp.status_code == 422


@respx.mock
async def test_phone_route_starts_call(client, authed):
    respx.post(f"{BASE}/call").mock(
        return_value=httpx.Response(200, json={"status": "queued", "execution_id": "ex-9"})
    )
    resp = await client.post("/api/v1/calls/phone", json={"phone": "+919876543210"})
    assert resp.status_code == 200
    assert resp.json()["execution_id"] == "ex-9"
    async with get_sessionmaker()() as s:
        cs = await s.get(CallSession, resp.json()["call_session_id"])
    assert cs.bolna_execution_id == "ex-9" and cs.channel == "phone"


@respx.mock
async def test_end_fetches_execution_and_revokes(client, authed):
    respx.post(f"{BASE}/call").mock(return_value=httpx.Response(200, json={"execution_id": "ex-10"}))
    respx.get(f"{BASE}/executions/ex-10").mock(
        return_value=httpx.Response(
            200, json={"id": "ex-10", "status": "completed", "transcript": "user: hi\nagent: hello"}
        )
    )
    cs_id = (await client.post("/api/v1/calls/phone", json={"phone": "+919876543210"})).json()[
        "call_session_id"
    ]
    resp = await client.post(f"/api/v1/calls/{cs_id}/end")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["transcript"] == "user: hi\nagent: hello"
    async with get_sessionmaker()() as s:
        assert (await s.get(CallSession, cs_id)).revoked_at is not None


async def test_end_without_execution_id_revokes_and_reports_missing_transcript(client, authed):
    from app.services.call_sessions import CallSessionService

    async with get_sessionmaker()() as s:
        cs, _ = await CallSessionService(s).create(authed.id, "web")
        await s.commit()
    resp = await client.post(f"/api/v1/calls/{cs.id}/end")
    assert resp.status_code == 200
    assert resp.json()["transcript"] is None
    assert resp.json()["transcript_note"]


async def test_other_users_call_404(client, make_user, login):
    from app.services.call_sessions import CallSessionService

    a, _ = await make_user()
    async with get_sessionmaker()() as s:
        cs, _ = await CallSessionService(s).create(a.id, "web")
        await s.commit()
    b, pw = await make_user()
    await login(b, pw)
    assert (await client.get(f"/api/v1/calls/{cs.id}")).status_code == 404
    assert (await client.post(f"/api/v1/calls/{cs.id}/end")).status_code == 404
    assert all(c["id"] != str(cs.id) for c in (await client.get("/api/v1/calls")).json())


@respx.mock
async def test_web_session_stores_run_id_and_end_uses_it_for_transcript(client, authed, monkeypatch):
    monkeypatch.setattr(get_settings(), "BOLNA_WEB_CALL_SESSION_PATH", "/web-call/freeswitch-session")
    respx.post(f"{BASE}/web-call/freeswitch-session").mock(
        return_value=httpx.Response(
            200, json={"run_id": "run-77", "agent_id": "agent-123", "expires_in": 120}
        )
    )
    respx.get(f"{BASE}/executions/run-77").mock(
        return_value=httpx.Response(
            200, json={"id": "run-77", "status": "completed", "transcript": "user: hi"}
        )
    )
    cs_id = (await client.post("/api/v1/calls/web-session")).json()["call_session_id"]
    async with get_sessionmaker()() as s:
        cs = await s.get(CallSession, cs_id)
    assert cs.bolna_run_id == "run-77"
    body = (await client.post(f"/api/v1/calls/{cs_id}/end")).json()
    assert body["transcript"] == "user: hi"
