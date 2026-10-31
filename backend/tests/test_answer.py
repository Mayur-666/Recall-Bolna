from datetime import date

import pytest

from app.core.config import get_settings
from app.integrations.model_client import ModelError
from app.services.answer import NO_MEMORY, compose_answer, fallback_answer
from tests.fakes import FakeModelClient
from tests.test_retrieval import seed


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    from app.integrations import model_client

    model = FakeModelClient()
    monkeypatch.setattr(model_client, "get_model_client", lambda: model)
    monkeypatch.setattr(get_settings(), "RETRIEVAL_MIN_VECTOR_SIM", 0.35)
    return model


async def _login(client, make_user):
    user, pw = await make_user()
    assert (await client.post("/api/v1/auth/login", json={"email": user.email, "password": pw})).status_code == 200
    return user


async def test_answer_is_written_from_results(client, make_user, fake_model):
    user = await _login(client, make_user)
    await seed(user, "API sync", date(2026, 10, 16), chunks=["Priya: We should use WebSockets for live updates."], speakers={0: ["Priya"]})
    fake_model.chat_fn = lambda system, user_msg: {"answer": "In API sync, Priya suggested WebSockets."}

    resp = await client.post("/api/v1/search/answer", json={"question": "What did Priya say about WebSockets?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["status"] == "found"
    assert body["answer"] == "In API sync, Priya suggested WebSockets."
    system, user_msg = fake_model.chat_calls[-1]
    assert "ONLY from the search results" in system
    assert "WebSockets" in user_msg  # the results are what the model sees


async def test_no_reliable_memory_never_calls_the_model(client, make_user, fake_model):
    await _login(client, make_user)
    resp = await client.post("/api/v1/search/answer", json={"question": "Who is our accountant?"})
    assert resp.json()["answer"].startswith(NO_MEMORY)
    assert fake_model.chat_calls == []


async def test_model_failure_falls_back_to_the_top_result(client, make_user, fake_model):
    user = await _login(client, make_user)
    await seed(user, "API sync", date(2026, 10, 16), chunks=["Priya: We should use WebSockets for live updates."], speakers={0: ["Priya"]})

    def boom(system, user_msg):
        raise ModelError("down")

    fake_model.chat_fn = boom
    resp = await client.post("/api/v1/search/answer", json={"question": "What did Priya say about WebSockets?"})
    assert resp.status_code == 200
    assert resp.json()["answer"].startswith("In API sync")


async def test_answer_requires_login(client):
    assert (await client.post("/api/v1/search/answer", json={"question": "x"})).status_code == 401


def test_fallback_prefers_the_newer_decision():
    from app.schemas.search import SearchResult

    def ev(ref, title, statement, state=None, by=None):
        return {
            "ref": ref, "kind": "decision", "conversation_id": "00000000-0000-0000-0000-000000000000",
            "conversation_title": title, "conversation_date": "2026-10-19", "relative_date": "12 days ago",
            "speaker": "Mayur", "statement": statement, "excerpt": statement, "decision_state": state,
            "superseded_by_ref": by, "conflict": False, "owner": None, "owner_is_user": False, "due_date": None,
            "score": 0.0, "vector_similarity": None, "related_to_ref": None, "weak": False,
        }

    r = SearchResult.model_validate({
        "status": "found", "memory_count": 2, "conversation_count": 2, "pending_conversations": [],
        "failed_conversations": [], "guidance": "", "timings_ms": {}, "degraded": False,
        "results": [ev("m:ecs", "Deployment planning", "Use AWS ECS", "superseded", "m:render"),
                    ev("m:render", "Deployment follow-up", "Move the beta to Render", "decided")],
    })
    assert "Render" in fallback_answer(r) and "Deployment follow-up" in fallback_answer(r)
