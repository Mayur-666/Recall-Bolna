import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.db.session import get_db
from app.models import Conversation, User
from app.repositories.conversations import ConversationsRepo
from app.repositories.memory_items import MemoryItemsRepo
from app.repositories.segments import SegmentsRepo
from app.schemas.conversation import ConversationDetail, ConversationOut, MemoryItemOut, SegmentOut
from app.services.ingestion import IngestionService, decode_upload

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _split_participants(raw: str | None) -> list[str]:
    if not raw:
        return []
    names = [p.strip() for p in raw.split(",") if p.strip()]
    return list(dict.fromkeys(names))[:20]


@router.post("", status_code=201, response_model=ConversationOut)
async def create_conversation(
    title: str = Form(min_length=1, max_length=200),
    conversation_date: date = Form(),
    participants: str | None = Form(None, max_length=2000),
    self_speaker: str | None = Form(None, max_length=120),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    if file is not None and file.filename:
        data = await file.read(get_settings().MAX_UPLOAD_BYTES + 1)
        body, source, filename = decode_upload(file.filename, data), "upload", file.filename
    elif text is not None:
        body, source, filename = text, "paste", None
    else:
        raise ValidationAppError("Provide transcript text or a file.")

    conv = await IngestionService(db).create(
        user_id=user.id,
        title=title,
        conversation_date=conversation_date,
        participants=_split_participants(participants),
        self_speaker=(self_speaker or "").strip() or None,
        text=body,
        source_type=source,
        filename=filename,
    )
    await db.commit()
    return conv


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, pattern="^(queued|processing|ready|failed)$"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Conversation]:
    return list(await ConversationsRepo(db).list_for_user(user.id, q, status))


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conv = await IngestionService(db).get(user.id, conversation_id)
    segments = await SegmentsRepo(db).list_for_conversation(user.id, conversation_id)
    items = await MemoryItemsRepo(db).list_for_conversation(user.id, conversation_id)
    base = ConversationOut.model_validate(conv).model_dump()
    return ConversationDetail(
        **base,
        transcript_text=conv.transcript_text,
        segments=[SegmentOut.model_validate(s) for s in segments],
        memory_items=[MemoryItemOut.model_validate(m) for m in items],
    )


@router.post("/{conversation_id}/retry", response_model=ConversationOut)
async def retry_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    conv = await IngestionService(db).retry(user.id, conversation_id)
    await db.commit()
    return conv


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await IngestionService(db).delete(user.id, conversation_id)
    await db.commit()
    return Response(status_code=204)
