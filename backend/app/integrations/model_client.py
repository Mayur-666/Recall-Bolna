"""One client for the backend's own model needs: embeddings and structured extraction.

Talks to any OpenAI-compatible endpoint (Ollama by default). This is NOT the voice
agent's LLM; Bolna owns that. Configured only through environment variables.
"""

import json
import logging
import math
from functools import lru_cache
from typing import Any, Literal, Protocol

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class ModelError(Exception):
    pass


class EmbeddingTimeout(ModelError):
    pass


class ModelClientProtocol(Protocol):
    async def embed(
        self, texts: list[str], kind: Literal["query", "document"], timeout_s: float | None = None
    ) -> list[list[float]]: ...

    async def chat_json(
        self, system: str, user: str, json_schema: dict[str, Any], temperature: float = 0.0
    ) -> dict[str, Any]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


class ModelClient:
    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self.settings = get_settings()
        self._http = http or self._new_http()

    def _new_http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.MODEL_BASE_URL,
            headers={"Authorization": f"Bearer {self.settings.MODEL_API_KEY}"},
            timeout=120.0,
        )

    async def _recycle_http(self) -> None:
        # A request aborted by our timeout leaves its pooled connection stalling the next
        # calls (measured on Ollama: ~0.4-0.6 s or another timeout). Start clean instead.
        old, self._http = self._http, self._new_http()
        await old.aclose()

    async def _post(self, path: str, payload: dict[str, Any], timeout: float | None = None) -> httpx.Response:
        kwargs: dict[str, Any] = {"json": payload}
        if timeout is not None:
            kwargs["timeout"] = timeout
        try:
            return await self._http.post(path, **kwargs)
        except httpx.TimeoutException:
            raise
        except httpx.TransportError as exc:
            # A keep-alive connection the server already dropped (Ollama unloading a model, a container
            # restart) fails the next request with ReadError/RemoteProtocolError. That used to fail the
            # whole ingestion job; one retry on a fresh connection is enough.
            log.warning("model request %s failed (%s); retrying on a fresh connection", path, type(exc).__name__)
            await self._recycle_http()
            return await self._http.post(path, **kwargs)

    async def embed(
        self,
        texts: list[str],
        kind: Literal["query", "document"],
        timeout_s: float | None = None,
    ) -> list[list[float]]:
        s = self.settings
        prefix = s.EMBED_QUERY_PREFIX if kind == "query" else s.EMBED_DOC_PREFIX
        payload = {"model": s.EMBED_MODEL, "input": [prefix + t for t in texts]}
        try:
            resp = await self._post("/embeddings", payload, timeout_s or 60.0)
        except httpx.TimeoutException as exc:
            await self._recycle_http()
            raise EmbeddingTimeout("embedding request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelError(f"embedding request failed: {type(exc).__name__}") from exc
        if resp.status_code != 200:
            raise ModelError(f"embedding endpoint returned {resp.status_code}")

        rows = sorted(resp.json()["data"], key=lambda r: r["index"])
        vectors = [r["embedding"] for r in rows]
        for v in vectors:
            if len(v) != s.EMBED_DIM:
                raise ModelError(
                    f"embedding dimension {len(v)} != EMBED_DIM {s.EMBED_DIM}; "
                    "the configured model doesn't match the database"
                )
        return [_normalize(v) for v in vectors]

    async def chat_json(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        payload = {
            "model": self.settings.EXTRACT_MODEL,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "out", "schema": json_schema, "strict": True},
            },
        }
        for attempt in (1, 2):
            try:
                resp = await self._post("/chat/completions", payload)
            except httpx.HTTPError as exc:
                raise ModelError(f"chat request failed: {type(exc).__name__}") from exc
            if resp.status_code != 200:
                raise ModelError(f"chat endpoint returned {resp.status_code}")
            content = resp.json()["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            log.warning("model returned invalid JSON (attempt %d)", attempt)
        raise ModelError("model did not return valid JSON after a retry")

    async def warm_up(self) -> None:
        """Load the embedding model before the first real query. Failure is non-fatal."""
        try:
            await self.embed(["warm"], kind="query", timeout_s=60.0)
        except ModelError as exc:
            log.warning("model warm-up failed: %s", exc)


@lru_cache
def get_model_client() -> ModelClient:
    return ModelClient()
