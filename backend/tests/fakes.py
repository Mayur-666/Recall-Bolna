"""Test-only fakes. Never imported by application code."""

import hashlib
import math
import re
from collections import deque
from typing import Any, Literal

from app.core.config import get_settings
from app.integrations.model_client import EmbeddingTimeout

_WORD = re.compile(r"[a-z0-9]+")


def bow_vector(text: str, dim: int | None = None) -> list[float]:
    """Deterministic hashed bag-of-words embedding: shared words => higher cosine."""
    dim = dim or get_settings().EMBED_DIM
    vec = [0.0] * dim
    for word in _WORD.findall(text.lower()):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class FakeModelClient:
    def __init__(self) -> None:
        self.chat_responses: deque[dict[str, Any] | Exception] = deque()
        self.embed_fail: Exception | None = None
        self.embed_timeout = False
        self.embed_calls: list[tuple[list[str], str]] = []
        self.chat_calls: list[tuple[str, str]] = []
        self.chat_fn: Any = None  # optional callable(system, user) -> dict

    async def embed(
        self, texts: list[str], kind: Literal["query", "document"], timeout_s: float | None = None
    ) -> list[list[float]]:
        self.embed_calls.append((texts, kind))
        if self.embed_timeout:
            raise EmbeddingTimeout("fake timeout")
        if self.embed_fail:
            raise self.embed_fail
        return [bow_vector(t) for t in texts]

    async def chat_json(
        self, system: str, user: str, json_schema: dict[str, Any], temperature: float = 0.0
    ) -> dict[str, Any]:
        self.chat_calls.append((system, user))
        if self.chat_fn is not None:
            result: dict[str, Any] = self.chat_fn(system, user)
            return result
        if not self.chat_responses:
            return {"items": []}
        nxt = self.chat_responses.popleft()
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    async def warm_up(self) -> None:
        return None
