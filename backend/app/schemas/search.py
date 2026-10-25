import uuid
from datetime import date

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    standalone_query: str | None = Field(None, max_length=500)
    from_date: date | None = None
    to_date: date | None = None
    previous_result_ref: str | None = Field(None, max_length=40)


class Evidence(BaseModel):
    ref: str
    kind: str  # "chunk" or a memory kind
    conversation_id: uuid.UUID
    conversation_title: str
    conversation_date: date
    relative_date: str
    speaker: str | None = None
    statement: str | None = None
    excerpt: str
    decision_state: str | None = None
    superseded_by_ref: str | None = None
    conflict: bool = False
    owner: str | None = None
    owner_is_user: bool = False
    due_date: date | None = None
    score: float = 0.0
    weak: bool = False


class SearchResult(BaseModel):
    status: str  # found | no_reliable_memory | ambiguous | error
    results: list[Evidence]
    memory_count: int
    conversation_count: int
    pending_conversations: list[str]
    failed_conversations: list[str]
    guidance: str
    timings_ms: dict[str, float]
    degraded: bool = False


class SourceLine(BaseModel):
    speaker: str | None
    text: str


class SourceContext(BaseModel):
    ref: str
    conversation_title: str
    conversation_date: date
    lines: list[dict[str, str | None]]


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    from_date: date | None = None
    to_date: date | None = None
