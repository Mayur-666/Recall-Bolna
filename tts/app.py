"""Local text-to-speech for Recall: Kokoro-82M, default voice af_heart.

The weights and voices are baked into the image at build time (fetch_model.py, pinned revision), and
loaded from KOKORO_DIR, so the service runs fully offline.
"""

import io
import logging
import os
import threading
import time
import wave
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

log = logging.getLogger("recall.tts")
logging.basicConfig(level=logging.INFO)

KOKORO_DIR = Path(os.environ.get("KOKORO_DIR", "/models/kokoro"))
DEFAULT_VOICE = os.environ.get("KOKORO_VOICE", "af_heart")
SAMPLE_RATE = 24000

app = FastAPI(title="Recall TTS (Kokoro)")
_lock = threading.Lock()  # one synthesis at a time; Kokoro isn't re-entrant
_pipeline = None
_voices: dict[str, object] = {}


def pipeline():
    global _pipeline
    if _pipeline is None:
        from kokoro import KModel, KPipeline

        config, weights = KOKORO_DIR / "config.json", KOKORO_DIR / "kokoro-v1_0.pth"
        started = time.perf_counter()
        model = KModel(repo_id="hexgrad/Kokoro-82M", config=str(config), model=str(weights)).eval()
        _pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M", model=model)
        log.info("Kokoro loaded from %s in %.1fs", KOKORO_DIR, time.perf_counter() - started)
    return _pipeline


def available_voices() -> list[str]:
    return sorted(p.stem for p in (KOKORO_DIR / "voices").glob("*.pt"))


def voice(name: str):
    """The voice tensor for one of the voices baked into the image."""
    if name not in _voices:
        path = KOKORO_DIR / "voices" / f"{name}.pt"
        if not path.exists():
            raise HTTPException(400, f"unknown voice {name!r}; available: {', '.join(available_voices())}")
        import torch

        _voices[name] = torch.load(str(path), weights_only=True)
    return _voices[name]


def to_wav(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str = Field(DEFAULT_VOICE, pattern=r"^[a-z]{2}_[a-z]+$")
    speed: float = Field(1.0, ge=0.5, le=2.0)


@app.on_event("startup")
def warm() -> None:
    # Load the model and default voice up front so the first answer isn't slow.
    try:
        with _lock:
            for _ in pipeline()("Ready.", voice=voice(DEFAULT_VOICE)):
                pass
    except Exception:
        log.exception("Kokoro warm-up failed")


@app.get("/health")
def health() -> Response:
    """200 once the model is loaded; 503 if it failed, so Recall falls back to the browser voice."""
    import json

    body = {"ok": _pipeline is not None, "voice": DEFAULT_VOICE, "voices": available_voices()}
    return Response(json.dumps(body), status_code=200 if body["ok"] else 503, media_type="application/json")


@app.post("/synthesize")
def synthesize(body: SpeakRequest) -> Response:
    started = time.perf_counter()
    try:
        with _lock:
            chunks = [a.numpy() if hasattr(a, "numpy") else a for _, _, a in pipeline()(body.text, voice=voice(body.voice), speed=body.speed) if a is not None]
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("synthesis failed")
        raise HTTPException(500, f"synthesis failed: {type(exc).__name__}") from exc
    if not chunks:
        raise HTTPException(500, "Kokoro produced no audio")
    audio = np.concatenate(chunks)
    log.info("synthesized %d chars -> %.1fs audio in %.2fs", len(body.text), len(audio) / SAMPLE_RATE, time.perf_counter() - started)
    return Response(to_wav(audio), media_type="audio/wav", headers={"Cache-Control": "no-store"})
