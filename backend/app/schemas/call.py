import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PhoneCallRequest(BaseModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$", description="E.164, e.g. +919876543210")


class WebSessionOut(BaseModel):
    call_session_id: uuid.UUID
    session: dict[str, Any]


class PhoneCallOut(BaseModel):
    call_session_id: uuid.UUID
    execution_id: str


class ToolCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_name: str
    original_question: str | None
    standalone_query: str | None
    result_status: str
    result: dict[str, Any]
    timings_ms: dict[str, Any]
    created_at: datetime


class CallSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: str
    status: str
    bolna_execution_id: str | None
    created_at: datetime
    ended_at: datetime | None
    transcript: str | None
    transcript_note: str | None = None


class CallSessionDetail(CallSessionOut):
    tool_calls: list[ToolCallOut]
