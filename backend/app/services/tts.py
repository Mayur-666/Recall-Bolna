"""Speech for typed-question answers.

First choice: the local Kokoro-82M service (compose service "tts", voice af_heart): natural, offline, free.
Alternative: the Bolna agent's own Cartesia voice. Bolna has no standalone "speak this text" API, so that
calls Cartesia directly with the agent's configured voice; it needs CARTESIA_API_KEY. If neither is
available, the browser's own speech synthesis is used (decided in the web app).
"""

import logging
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.integrations.bolna_client import BolnaClient, BolnaError

log = logging.getLogger(__name__)

CARTESIA_VERSION = "2026-08-14"
DEFAULT_MODEL = "sonic-3.6"
AGENT_VOICE_TTL_S = 600


class TtsUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Voice:
    voice_id: str
    model: str
    name: str | None
    language: str


_cached: tuple[float, Voice | None] | None = None


async def agent_voice() -> Voice | None:
    """The voice to speak with: TTS_VOICE_ID if set, else the Bolna agent's Cartesia voice (cached)."""
    global _cached
    s = get_settings()
    if s.TTS_VOICE_ID:
        return Voice(s.TTS_VOICE_ID, s.TTS_MODEL or DEFAULT_MODEL, None, "en")
    if _cached and time.monotonic() - _cached[0] < AGENT_VOICE_TTL_S:
        return _cached[1]
    voice: Voice | None = None
    if s.BOLNA_API_KEY and s.BOLNA_AGENT_ID:
        try:
            agent = await BolnaClient().get_agent(s.BOLNA_AGENT_ID)
            syn = (agent.get("agent_config", agent)["tasks"][0]["tools_config"] or {}).get("synthesizer") or {}
            cfg = syn.get("provider_config") or {}
            if syn.get("provider") == "cartesia" and cfg.get("voice_id"):
                voice = Voice(
                    cfg["voice_id"], s.TTS_MODEL or cfg.get("model") or DEFAULT_MODEL, cfg.get("voice"), cfg.get("language") or "en"
                )
            else:
                log.info("agent synthesizer is %r, not cartesia; set TTS_VOICE_ID to choose a voice", syn.get("provider"))
        except (BolnaError, httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            log.warning("could not read the agent's voice from Bolna: %s", type(exc).__name__)
    _cached = (time.monotonic(), voice)
    return voice


async def _kokoro_healthy() -> bool:
    url = get_settings().KOKORO_URL
    if not url:
        return False
    try:
        async with httpx.AsyncClient(base_url=url, timeout=2.0) as http:
            r = await http.get("/health")
        return r.status_code == 200
    except httpx.HTTPError:
        return False


async def _kokoro(text: str) -> bytes:
    s = get_settings()
    try:
        async with httpx.AsyncClient(base_url=s.KOKORO_URL, timeout=30.0) as http:
            resp = await http.post("/synthesize", json={"text": text, "voice": s.KOKORO_VOICE})
    except httpx.HTTPError as exc:
        raise TtsUnavailable(f"Kokoro unreachable: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        raise TtsUnavailable(f"Kokoro returned {resp.status_code}: {resp.text[:200]}")
    return resp.content


async def tts_status() -> dict[str, object]:
    s = get_settings()
    if await _kokoro_healthy():
        return {"available": True, "provider": "kokoro", "voice": s.KOKORO_VOICE, "reason": None}
    voice = await agent_voice() if s.CARTESIA_API_KEY else None
    if s.CARTESIA_API_KEY and voice:
        return {"available": True, "provider": "cartesia", "voice": voice.name, "reason": None}
    reason = "Kokoro service not running" if s.KOKORO_URL else "no TTS configured"
    if s.CARTESIA_API_KEY and not voice:
        reason += "; no Cartesia voice configured"
    return {"available": False, "provider": None, "voice": None, "reason": reason}


async def synthesize(text: str) -> tuple[bytes, str]:
    """(audio, media type): Kokoro WAV when the local service is up, else the agent's Cartesia voice as MP3."""
    s = get_settings()
    if s.KOKORO_URL:
        try:
            return await _kokoro(text), "audio/wav"
        except TtsUnavailable as exc:
            if not s.CARTESIA_API_KEY:
                raise
            log.warning("%s; falling back to Cartesia", exc)
    return await _cartesia(text), "audio/mpeg"


async def _cartesia(text: str) -> bytes:
    """MP3 audio of `text` in the Bolna agent's Cartesia voice."""
    s = get_settings()
    if not s.CARTESIA_API_KEY:
        raise TtsUnavailable("no TTS configured (Kokoro not running, no CARTESIA_API_KEY)")
    voice = await agent_voice()
    if voice is None:
        raise TtsUnavailable("no Cartesia voice configured")
    body = {
        "model_id": voice.model,
        "transcript": text,
        "voice": {"id": voice.voice_id},
        "language": voice.language,
        "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
    }
    headers = {
        "Authorization": f"Bearer {s.CARTESIA_API_KEY}",
        "Cartesia-Version": CARTESIA_VERSION,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(base_url=s.CARTESIA_BASE_URL, timeout=20.0) as http:
            resp = await http.post("/tts/bytes", json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise TtsUnavailable(f"Cartesia unreachable: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        # Never echo the key; the body excerpt is Cartesia's error message.
        raise TtsUnavailable(f"Cartesia returned {resp.status_code}: {resp.text[:200]}")
    return resp.content
