"""Request bodies Bolna sends to Recall's custom tools.

Bolna substitutes %(name)s placeholders; optional params the LLM didn't fill can arrive
literally (e.g. "%(from_date)s") or empty, so those are normalized to None. Unknown
fields (e.g. a model-invented user_id) are rejected.
"""

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_PLACEHOLDER = re.compile(r"^%\(\w+\)[sif]$")


def clean_param(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or _PLACEHOLDER.match(text) or text.lower() in {"none", "null", "undefined"}:
        return None
    return text


class _ToolBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recall_session: str | None = Field(None, max_length=200)
    execution_id: str | None = Field(None, max_length=64)

    @field_validator("recall_session", "execution_id", mode="before")
    @classmethod
    def _clean(cls, v: Any) -> str | None:
        return clean_param(v)


class SearchToolRequest(_ToolBase):
    question: str = Field(min_length=1, max_length=500)
    standalone_query: str | None = Field(None, max_length=500)
    from_date: date | None = None
    to_date: date | None = None
    previous_result_ref: str | None = Field(None, max_length=40)

    @field_validator("standalone_query", "previous_result_ref", mode="before")
    @classmethod
    def _clean_text(cls, v: Any) -> str | None:
        return clean_param(v)

    @field_validator("from_date", "to_date", mode="before")
    @classmethod
    def _clean_date(cls, v: Any) -> date | None:
        text = clean_param(v)
        if text is None:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None  # a malformed date from the LLM shouldn't break the call


class SourceToolRequest(_ToolBase):
    ref: str = Field(min_length=3, max_length=40)


class SaveMemoryToolRequest(_ToolBase):
    # What the user asked Recall to remember, in their own (first-person) words.
    note: str = Field(min_length=3, max_length=1000)

    @field_validator("note", mode="before")
    @classmethod
    def _clean_note(cls, v: Any) -> str:
        return clean_param(v) or ""
