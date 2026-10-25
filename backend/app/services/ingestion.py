import hashlib
import re
import uuid
from datetime import date
from pathlib import PurePath

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, PayloadTooLargeError, ValidationAppError
from app.models import Conversation
from app.repositories.conversations import ConversationsRepo
from app.repositories.jobs import JobsRepo

ALLOWED_EXTENSIONS = {".txt", ".md", ".vtt", ".srt"}
_BLANK_RUNS = re.compile(r"\n{3,}")


def normalize_for_hash(text: str) -> str:
    """Whitespace and line-ending variants of the same transcript hash the same."""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified.split("\n")]
    return _BLANK_RUNS.sub("\n\n", "\n".join(lines)).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode()).hexdigest()


def decode_upload(filename: str, data: bytes) -> str:
    settings = get_settings()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError(f"File is larger than {settings.MAX_UPLOAD_BYTES} bytes.")
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationAppError(
            f"Unsupported file type. Use one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationAppError("File must be UTF-8 text.") from exc


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversations = ConversationsRepo(session)
        self.jobs = JobsRepo(session)

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        conversation_date: date,
        participants: list[str],
        self_speaker: str | None,
        text: str,
        source_type: str,
        filename: str | None,
        is_sample: bool = False,
    ) -> Conversation:
        settings = get_settings()
        if not text.strip():
            raise ValidationAppError("Transcript is empty.")
        if len(text) > settings.MAX_TRANSCRIPT_CHARS:
            raise ValidationAppError(f"Transcript is longer than {settings.MAX_TRANSCRIPT_CHARS} characters.")
        if self_speaker and self_speaker not in participants:
            raise ValidationAppError("'Which participant is you' must be one of the participants.")

        digest = content_hash(text)
        existing = await self.conversations.get_by_hash(user_id, digest)
        if existing is not None:
            raise ConflictError("This transcript was already added.", existing_id=str(existing.id))

        conv = Conversation(
            user_id=user_id,
            title=title.strip(),
            conversation_date=conversation_date,
            participants=participants,
            self_speaker=self_speaker or None,
            source_type=source_type,
            original_filename=filename,
            transcript_text=text,
            content_hash=digest,
            status="queued",
            is_sample=is_sample,
        )
        try:
            await self.conversations.add(conv)
        except IntegrityError as exc:  # concurrent duplicate
            await self.session.rollback()
            raise ConflictError("This transcript was already added.") from exc
        await self.jobs.enqueue(user_id, conv.id)
        return conv

    async def get(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
        conv = await self.conversations.get(user_id, conversation_id)
        if conv is None:
            raise NotFoundError("Conversation not found.")
        return conv

    async def retry(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
        conv = await self.get(user_id, conversation_id)
        if conv.status != "failed":
            raise ConflictError("Only failed conversations can be retried.")
        conv.status = "queued"
        conv.error_message = None
        await self.jobs.enqueue(user_id, conv.id)
        return conv

    async def delete(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        await self.get(user_id, conversation_id)
        await self.conversations.delete(user_id, conversation_id)
