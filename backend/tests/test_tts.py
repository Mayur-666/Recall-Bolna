import httpx
import respx

from app.core.config import get_settings
from app.services import tts


async def _login(client, make_user):
    user, pw = await make_user()
    assert (await client.post("/api/v1/auth/login", json={"email": user.email, "password": pw})).status_code == 200


async def test_tts_requires_login(client):
    assert (await client.get("/api/v1/tts/status")).status_code == 401
    assert (await client.post("/api/v1/tts", json={"text": "hi"})).status_code == 401


async def test_without_a_key_tts_is_unavailable_and_browser_speaks(client, make_user):
    await _login(client, make_user)
    status = (await client.get("/api/v1/tts/status")).json()
    assert status["available"] is False and status["reason"] == "no TTS configured"
    assert (await client.post("/api/v1/tts", json={"text": "hi"})).status_code == 503


@respx.mock
async def test_speaks_in_the_agents_cartesia_voice(client, make_user, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "CARTESIA_API_KEY", "sk_car_test")
    monkeypatch.setattr(s, "BOLNA_API_KEY", "bn-test")
    monkeypatch.setattr(s, "BOLNA_AGENT_ID", "agent-1")
    monkeypatch.setattr(tts, "_cached", None)
    respx.get(f"{s.BOLNA_BASE_URL}/v2/agent/agent-1").mock(
        return_value=httpx.Response(200, json={"agent_config": {"tasks": [{"tools_config": {"synthesizer": {
            "provider": "cartesia",
            "provider_config": {"voice_id": "voice-123", "model": "sonic-3.6", "voice": "Jacqueline", "language": "en"},
        }}}]}})
    )
    route = respx.post(f"{s.CARTESIA_BASE_URL}/tts/bytes").mock(return_value=httpx.Response(200, content=b"ID3fake-mp3"))
    await _login(client, make_user)

    status = (await client.get("/api/v1/tts/status")).json()
    assert status == {"available": True, "provider": "cartesia", "voice": "Jacqueline", "reason": None}
    resp = await client.post("/api/v1/tts", json={"text": "You're on Render."})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg" and resp.content == b"ID3fake-mp3"
    sent = route.calls.last.request
    import json
    payload = json.loads(sent.content)
    assert payload["voice"] == {"id": "voice-123"} and payload["model_id"] == "sonic-3.6"
    assert payload["transcript"] == "You're on Render."
    assert sent.headers["Authorization"] == "Bearer sk_car_test"
    assert sent.headers["Cartesia-Version"]


@respx.mock
async def test_cartesia_error_is_a_503_not_a_crash(client, make_user, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "CARTESIA_API_KEY", "sk_car_test")
    monkeypatch.setattr(s, "TTS_VOICE_ID", "voice-123")
    respx.post(f"{s.CARTESIA_BASE_URL}/tts/bytes").mock(return_value=httpx.Response(401, text="invalid key"))
    await _login(client, make_user)
    resp = await client.post("/api/v1/tts", json={"text": "hello"})
    assert resp.status_code == 503
    assert "sk_car_test" not in resp.text


@respx.mock
async def test_kokoro_is_preferred_and_returns_wav(client, make_user, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "KOKORO_URL", "http://tts:8880")
    monkeypatch.setattr(s, "CARTESIA_API_KEY", "sk_car_test")  # present, but Kokoro wins
    respx.get("http://tts:8880/health").mock(return_value=httpx.Response(200, json={"ok": True}))
    kokoro = respx.post("http://tts:8880/synthesize").mock(return_value=httpx.Response(200, content=b"RIFFfake-wav"))
    cartesia = respx.post(f"{s.CARTESIA_BASE_URL}/tts/bytes").mock(return_value=httpx.Response(200, content=b"mp3"))
    await _login(client, make_user)

    status = (await client.get("/api/v1/tts/status")).json()
    assert status == {"available": True, "provider": "kokoro", "voice": "af_heart", "reason": None}
    resp = await client.post("/api/v1/tts", json={"text": "You're on Render."})
    assert resp.status_code == 200 and resp.headers["content-type"] == "audio/wav"
    assert resp.content == b"RIFFfake-wav"
    import json

    assert json.loads(kokoro.calls.last.request.content) == {"text": "You're on Render.", "voice": "af_heart"}
    assert not cartesia.called


@respx.mock
async def test_kokoro_down_without_cartesia_is_unavailable(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "KOKORO_URL", "http://tts:8880")
    respx.get("http://tts:8880/health").mock(side_effect=httpx.ConnectError("down"))
    respx.post("http://tts:8880/synthesize").mock(side_effect=httpx.ConnectError("down"))
    await _login(client, make_user)
    status = (await client.get("/api/v1/tts/status")).json()
    assert status["available"] is False and "Kokoro" in status["reason"]
    assert (await client.post("/api/v1/tts", json={"text": "hi"})).status_code == 503

