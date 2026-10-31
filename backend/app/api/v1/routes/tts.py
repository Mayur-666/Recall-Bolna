from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.api.deps import current_user
from app.core.errors import ServiceUnavailableError
from app.models import User
from app.services.tts import TtsUnavailable, synthesize, tts_status

router = APIRouter(prefix="/tts", tags=["tts"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.get("/status")
async def status(user: User = Depends(current_user)) -> dict[str, Any]:
    """Whether typed answers can be spoken by Kokoro or the agent's Cartesia voice (else the browser speaks)."""
    return await tts_status()


@router.post("", response_class=Response)
async def speak(body: SpeakRequest, user: User = Depends(current_user)) -> Response:
    try:
        audio, media_type = await synthesize(body.text)
    except TtsUnavailable as exc:
        raise ServiceUnavailableError(f"Voice unavailable: {exc}") from exc
    return Response(content=audio, media_type=media_type, headers={"Cache-Control": "no-store"})
