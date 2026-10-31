import json
import math

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.integrations.model_client import EmbeddingTimeout, ModelClient, ModelError

BASE = get_settings().MODEL_BASE_URL
DIM = get_settings().EMBED_DIM


def _emb_response(n: int, dim: int = DIM, value: float = 3.0) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"index": i, "embedding": [value] * dim} for i in range(n)]})


@respx.mock
async def test_embed_adds_query_prefix():
    route = respx.post(f"{BASE}/embeddings").mock(return_value=_emb_response(1))
    await ModelClient().embed(["what did we decide"], kind="query")
    sent = json.loads(route.calls[0].request.content)
    assert sent["input"] == ["search_query: what did we decide"]


@respx.mock
async def test_embed_adds_document_prefix():
    route = respx.post(f"{BASE}/embeddings").mock(return_value=_emb_response(2))
    await ModelClient().embed(["a", "b"], kind="document")
    sent = json.loads(route.calls[0].request.content)
    assert sent["input"] == ["search_document: a", "search_document: b"]


@respx.mock
async def test_embed_normalizes():
    respx.post(f"{BASE}/embeddings").mock(return_value=_emb_response(1))
    [vec] = await ModelClient().embed(["x"], kind="query")
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-6)


@respx.mock
async def test_embed_dim_mismatch_raises():
    respx.post(f"{BASE}/embeddings").mock(return_value=_emb_response(1, dim=DIM + 1))
    with pytest.raises(ModelError, match="dimension"):
        await ModelClient().embed(["x"], kind="query")


@respx.mock
async def test_embed_timeout_raises_EmbeddingTimeout():
    respx.post(f"{BASE}/embeddings").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(EmbeddingTimeout):
        await ModelClient().embed(["x"], kind="query", timeout_s=0.1)


@respx.mock
async def test_embed_http_error_raises_ModelError():
    respx.post(f"{BASE}/embeddings").mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(ModelError):
        await ModelClient().embed(["x"], kind="query")


def _chat(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@respx.mock
async def test_chat_json_sends_schema_and_parses():
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=_chat('{"ok": true}'))
    out = await ModelClient().chat_json("sys", "user", {"type": "object"})
    assert out == {"ok": True}
    sent = json.loads(route.calls[0].request.content)
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert sent["temperature"] == 0.0


@respx.mock
async def test_chat_json_retries_once_on_bad_json():
    route = respx.post(f"{BASE}/chat/completions").mock(side_effect=[_chat("not json"), _chat('{"a": 1}')])
    assert await ModelClient().chat_json("s", "u", {"type": "object"}) == {"a": 1}
    assert route.call_count == 2


@respx.mock
async def test_chat_json_gives_up_after_second_bad_json():
    respx.post(f"{BASE}/chat/completions").mock(side_effect=[_chat("nope"), _chat("still nope")])
    with pytest.raises(ModelError):
        await ModelClient().chat_json("s", "u", {"type": "object"})


@respx.mock
async def test_embed_timeout_recycles_http_connection():
    # An aborted request leaves the pooled connection stalling the next 1-2 calls (measured
    # against real Ollama: 393-569 ms and one timeout); a fresh client avoids that.
    respx.post(f"{BASE}/embeddings").mock(side_effect=[httpx.ReadTimeout("slow"), _emb_response(1)])
    client = ModelClient()
    before = client._http
    with pytest.raises(EmbeddingTimeout):
        await client.embed(["x"], kind="query", timeout_s=0.1)
    assert client._http is not before
    assert before.is_closed
    await client.embed(["y"], kind="query")


@respx.mock
async def test_dropped_connection_is_retried_once_on_a_fresh_client():
    # Regression: a voice note failed ingestion with "embedding request failed: ReadError" right after a
    # backend restart, although Ollama was healthy.
    route = respx.post(f"{BASE}/embeddings").mock(side_effect=[httpx.ReadError("closed"), _emb_response(1)])
    client = ModelClient()
    before = client._http
    [vec] = await client.embed(["x"], kind="query")
    assert len(vec) == DIM and route.call_count == 2
    assert client._http is not before and before.is_closed


@respx.mock
async def test_chat_retries_dropped_connection_too():
    respx.post(f"{BASE}/chat/completions").mock(side_effect=[httpx.RemoteProtocolError("eof"), _chat('{"a": 1}')])
    assert await ModelClient().chat_json("s", "u", {"type": "object"}) == {"a": 1}


@respx.mock
async def test_connection_failing_twice_still_raises_ModelError():
    respx.post(f"{BASE}/embeddings").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(ModelError):
        await ModelClient().embed(["x"], kind="query")

