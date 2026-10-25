import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    conversation_date: date
    participants: list[str]
    self_speaker: str | None
    source_type: str
    original_filename: str | None
    status: str
    error_message: str | None
    attempts: int
    is_sample: bool
    created_at: datetime


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    speaker: str | None
    text: str
    char_start: int
    char_end: int


class MemoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    kind: str
    topic: str
    statement: str
    speaker: str | None
    owner: str | None
    owner_is_user: bool
    due_date: date | None
    decision_state: str | None
    superseded_by_id: uuid.UUID | None
    evidence_quote: str
    char_start: int
    char_end: int


class ConversationDetail(ConversationOut):
    transcript_text: str
    segments: list[SegmentOut]
    memory_items: list[MemoryItemOut]
