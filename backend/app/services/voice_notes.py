"""Things the user tells Recall to remember during a call ("remember that the demo moved to Friday").

A voice note is stored as a one-line conversation spoken by the user, then goes through the same
ingestion pipeline as an uploaded transcript: chunks for search, extracted decisions/commitments/dates
whose quotes must match the note verbatim, and cross-conversation decision linking. So "we moved the
demo to Friday" can supersede an older demo decision, and "I'll send the deck" becomes the user's own
commitment.
"""

import re
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.models import Conversation, User
from app.services.ingestion import IngestionService

_NOT_NAME = re.compile(r"[^A-Za-z.'\- ]+")
TITLE_WORDS = 7


def speaker_label(display_name: str) -> str:
    """A label the transcript parser accepts as a speaker: letters, at most three words."""
    words = _NOT_NAME.sub(" ", display_name or "").split()
    words = [w for w in words if w[0].isalpha()][:3]
    return " ".join(w[:1].upper() + w[1:] for w in words) or "Me"


def note_title(note: str) -> str:
    words = note.split()
    head = " ".join(words[:TITLE_WORDS])
    return f"Voice note: {head}{'…' if len(words) > TITLE_WORDS else ''}"[:200]


async def save_voice_note(
    session: AsyncSession, user: User, note: str, today: date
) -> tuple[Conversation | None, bool]:
    """Queue the note for ingestion. Returns (conversation, created); created is False when the
    exact same note was already saved (the existing conversation is returned when known)."""
    label = speaker_label(user.display_name)
    text = f"{label}: {' '.join(note.split())}"
    try:
        conv = await IngestionService(session).create(
            user.id,
            note_title(note),
            today,
            [label],
            label,
            text,
            "voice",
            None,
        )
    except ConflictError as exc:
        existing_id = (exc.details or {}).get("existing_id")
        existing = await IngestionService(session).get(user.id, uuid.UUID(existing_id)) if existing_id else None
        return existing, False
    return conv, True
