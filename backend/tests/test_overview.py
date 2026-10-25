from datetime import date

from app.db.session import get_sessionmaker
from app.models import Conversation
from tests.test_retrieval import seed


async def test_overview_counts_and_needs_attention_scoped_to_user(client, make_user, login):
    user, pw = await make_user()
    other, _ = await make_user()
    await seed(user, "API sync", date(2026, 10, 16), chunks=["We decided to use WebSockets."],
               items=[{"topic": "transport", "statement": "Use WebSockets.", "quote": "We decided to use WebSockets.",
                       "state": "decided"},
                      {"kind": "action_item", "topic": "auth spec", "statement": "Mayur writes the auth spec.",
                       "quote": "We decided to use WebSockets.", "owner": "Mayur", "owner_is_user": True}])  # fmt: skip
    await seed(user, "Broken", date(2026, 10, 17), chunks=["x y z"], status="failed")
    await seed(other, "Other user's call", date(2026, 10, 18), chunks=["secret"])
    async with get_sessionmaker()() as s:
        conv = (
            await s.execute(Conversation.__table__.select().where(Conversation.title == "Broken"))
        ).first()
        await s.execute(
            Conversation.__table__.update()
            .where(Conversation.id == conv.id)
            .values(error_message="model down")
        )
        await s.commit()

    await login(user, pw)
    body = (await client.get("/api/v1/overview")).json()
    assert body["conversation_count"] == 1
    assert body["memory_count"] == 2
    assert [d["statement"] for d in body["recent_decisions"]] == ["Use WebSockets."]
    assert [a["statement"] for a in body["open_action_items"]] == ["Mayur writes the auth spec."]
    assert body["open_action_items"][0]["owner_is_user"] is True
    assert body["needs_attention"] == [
        {"id": str(conv.id), "title": "Broken", "status": "failed", "error": "model down"}
    ]


async def test_memories_filter_by_kind_and_state(client, make_user, login):
    user, pw = await make_user()
    await seed(user, "API sync", date(2026, 10, 16), chunks=["We decided to use WebSockets."],
               items=[{"topic": "transport", "statement": "Use WebSockets.", "quote": "We decided to use WebSockets.",
                       "state": "decided"},
                      {"topic": "pricing", "statement": "Maybe three tiers.", "quote": "We decided to use WebSockets.",
                       "state": "proposed"}])  # fmt: skip
    await login(user, pw)
    decided = (await client.get("/api/v1/memories?kind=decision&state=decided")).json()
    assert [m["statement"] for m in decided] == ["Use WebSockets."]
    assert decided[0]["conversation_title"] == "API sync"
    assert (await client.get("/api/v1/memories?state=bogus")).status_code == 422


async def test_overview_requires_auth(client):
    assert (await client.get("/api/v1/overview")).status_code == 401
