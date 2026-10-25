import uuid
from datetime import date

import pytest

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.db.session import get_sessionmaker
from app.models import Chunk, Conversation, MemoryItem
from app.services.retrieval import RetrievalService, SearchQuery
from tests.fakes import FakeModelClient, bow_vector

TODAY = date(2026, 10, 25)


@pytest.fixture(autouse=True)
def bow_thresholds(monkeypatch):
    # Bag-of-words test vectors score lower than real embeddings; real values are calibrated in eval.
    monkeypatch.setattr(get_settings(), "RETRIEVAL_MIN_VECTOR_SIM", 0.35)


async def seed(user, title, day, chunks=(), items=(), status="ready", speakers=None):
    """Insert a conversation with chunks/items directly (bypassing the worker)."""
    async with get_sessionmaker()() as s:
        transcript = "\n".join(chunks) or "placeholder text for the conversation"
        conv = Conversation(
            user_id=user.id, title=title, conversation_date=day, participants=[], source_type="paste",
            transcript_text=transcript, content_hash=uuid.uuid4().hex, status=status,
        )  # fmt: skip
        s.add(conv)
        await s.flush()
        pos = 0
        chunk_rows = []
        for i, text in enumerate(chunks):
            spk = (speakers or {}).get(i, [])
            row = Chunk(
                conversation_id=conv.id, user_id=user.id, seq=i, text=text, char_start=pos,
                char_end=pos + len(text), speakers=spk, embed_text=text, embedding=bow_vector(f"{title} {text}"),
            )  # fmt: skip
            pos += len(text) + 1
            chunk_rows.append(row)
        s.add_all(chunk_rows)
        item_rows = []
        for it in items:
            quote = it["quote"]
            start = transcript.find(quote) if quote in transcript else 0
            row = MemoryItem(
                conversation_id=conv.id, user_id=user.id, kind=it.get("kind", "decision"),
                topic=it["topic"], statement=it["statement"], speaker=it.get("speaker"), owner=it.get("owner"),
                owner_is_user=it.get("owner_is_user", False), decision_state=it.get("state"),
                evidence_quote=quote, char_start=start, char_end=start + len(quote),
                embedding=bow_vector(f"{it['topic']} {it['statement']} {quote}"),
                topic_embedding=bow_vector(it["topic"]),
            )  # fmt: skip
            item_rows.append(row)
        s.add_all(item_rows)
        await s.commit()
        return conv, chunk_rows, item_rows


async def search(user, question, model=None, **kw):
    async with get_sessionmaker()() as s:
        return await RetrievalService(s, model or FakeModelClient()).search(
            user.id, SearchQuery(question=question, **kw), TODAY
        )


async def test_exact_name_found_via_keyword(make_user):
    user, _ = await make_user()
    await seed(
        user, "API sync", date(2026, 10, 16),
        chunks=["Priya: We should use WebSockets for live updates.", "Mayur: The database is Postgres."],
        speakers={0: ["Priya"], 1: ["Mayur"]},
    )  # fmt: skip
    res = await search(user, "What did Priya say about WebSockets?")
    assert res.status == "found"
    assert "WebSockets" in res.results[0].excerpt
    assert res.results[0].speaker == "Priya"
    assert res.results[0].conversation_title == "API sync"
    assert res.results[0].relative_date == "on Friday, 16 October"


async def test_date_window_uses_conversation_date_not_created_at(make_user):
    user, _ = await make_user()
    await seed(user, "Old planning", date(2026, 9, 20), chunks=["We decided to ship the beta in March."])
    await seed(
        user, "Recent planning", date(2026, 10, 15), chunks=["We decided to ship the beta in November."]
    )
    res = await search(user, "What did we decide about the beta last week?")
    assert res.status == "found"
    assert {r.conversation_title for r in res.results} == {"Recent planning"}


async def test_explicit_dates_override_question(make_user):
    user, _ = await make_user()
    await seed(user, "Old planning", date(2026, 9, 20), chunks=["We decided to ship the beta in March."])
    res = await search(user, "beta ship decision", from_date=date(2026, 9, 1), to_date=date(2026, 9, 30))
    assert [r.conversation_title for r in res.results] == ["Old planning"]


async def test_superseded_decision_marked(make_user):
    user, _ = await make_user()
    _, _, (ecs,) = await seed(
        user, "Deploy planning", date(2026, 10, 5), chunks=["Let's go with AWS ECS for hosting."],
        items=[{"topic": "deployment provider", "statement": "Host on AWS ECS.",
                "quote": "Let's go with AWS ECS for hosting.", "state": "superseded"}],
    )  # fmt: skip
    _, _, (render,) = await seed(
        user, "Deploy follow-up", date(2026, 10, 20), chunks=["We're dropping ECS and moving to Render."],
        items=[{"topic": "deployment provider", "statement": "Move hosting to Render.",
                "quote": "We're dropping ECS and moving to Render.", "state": "decided"}],
    )  # fmt: skip
    async with get_sessionmaker()() as s:
        row = await s.get(MemoryItem, ecs.id)
        row.superseded_by_id = render.id
        await s.commit()

    res = await search(user, "Which deployment provider did we pick, ECS?")
    by_ref = {r.ref: r for r in res.results}
    assert f"m:{ecs.id}" in by_ref and f"m:{render.id}" in by_ref  # superseder pulled in
    assert by_ref[f"m:{ecs.id}"].decision_state == "superseded"
    assert by_ref[f"m:{ecs.id}"].superseded_by_ref == f"m:{render.id}"
    assert "changed" in res.guidance


async def _db_pair(user):
    _, _, (pg,) = await seed(
        user, "DB choice", date(2026, 10, 1), chunks=["We decided on Postgres as the database."],
        items=[{"topic": "database choice", "statement": "Use Postgres as the database.",
                "quote": "We decided on Postgres as the database.", "state": "decided"}],
    )  # fmt: skip
    _, _, (my,) = await seed(
        user, "Analytics sync", date(2026, 10, 22), chunks=["We decided on MySQL as the database."],
        items=[{"topic": "database choice", "statement": "Use MySQL as the database.",
                "quote": "We decided on MySQL as the database.", "state": "decided"}],
    )  # fmt: skip
    return pg, my


async def test_conflicting_pair_flagged_with_partner(make_user):
    user, _ = await make_user()
    pg, my = await _db_pair(user)
    async with get_sessionmaker()() as s:
        row = await s.get(MemoryItem, my.id)
        row.conflict_with_id = pg.id
        await s.commit()
    res = await search(user, "Which database did we choose, Postgres?")
    decided = {r.ref: r for r in res.results if r.kind == "decision"}
    assert set(decided) == {f"m:{pg.id}", f"m:{my.id}"}
    assert all(r.conflict for r in decided.values())
    assert "disagree" in res.guidance


async def test_same_topic_without_conflict_link_not_flagged(make_user):
    user, _ = await make_user()
    await _db_pair(user)
    res = await search(user, "Which database did we choose?")
    assert not any(r.conflict for r in res.results)
    assert "disagree" not in res.guidance


async def test_partner_items_marked_related_and_similarity_exposed(make_user):
    user, _ = await make_user()
    _, _, (ecs,) = await seed(
        user, "Deploy planning", date(2026, 10, 14), chunks=["Let's go with AWS ECS for hosting."],
        items=[{"topic": "deployment provider", "statement": "Host on AWS ECS.",
                "quote": "Let's go with AWS ECS for hosting.", "state": "superseded"}],
    )  # fmt: skip
    _, _, (render,) = await seed(
        user, "Deploy follow-up", date(2026, 10, 20), chunks=["Moving hosting over to Render now."],
        items=[{"topic": "hosting move", "statement": "Move hosting to Render.",
                "quote": "Moving hosting over to Render now.", "state": "decided"}],
    )  # fmt: skip
    async with get_sessionmaker()() as s:
        (await s.get(MemoryItem, ecs.id)).superseded_by_id = render.id
        await s.commit()
    res = await search(user, "What did we decide about AWS ECS hosting last week?")
    by_ref = {r.ref: r for r in res.results}
    assert by_ref[f"m:{render.id}"].related_to_ref == f"m:{ecs.id}"
    assert by_ref[f"m:{ecs.id}"].related_to_ref is None
    assert by_ref[f"m:{ecs.id}"].vector_similarity is not None


async def test_no_match_returns_no_reliable_memory_with_weak_flag(make_user):
    user, _ = await make_user()
    await seed(
        user, "API sync", date(2026, 10, 16), chunks=["Priya: We should use WebSockets for live updates."]
    )
    res = await search(user, "What did we decide about the office lease?")
    assert res.status == "no_reliable_memory"
    assert len(res.results) <= 1
    assert "don't have a reliable memory" in res.guidance


async def test_similar_unrelated_conversations_ambiguous_or_abstain(make_user):
    user, _ = await make_user()
    await seed(
        user, "Hiring sync", date(2026, 10, 10), chunks=["The launch date for the hiring portal is June 3."]
    )
    await seed(
        user, "Marketing sync", date(2026, 10, 11), chunks=["The launch date for the campaign is July 9."]
    )
    res = await search(user, "When is the launch date?")
    assert res.status in ("ambiguous", "no_reliable_memory")
    if res.status == "ambiguous":
        assert {r.conversation_title for r in res.results} >= {"Hiring sync", "Marketing sync"}
        assert "which conversation" in res.guidance


async def test_previous_result_ref_resolves_followup(make_user):
    user, _ = await make_user()
    _, chunks, _ = await seed(
        user, "API sync", date(2026, 10, 16),
        chunks=["Priya: We should use WebSockets for live updates.", "Mayur: Agreed, ship it."],
        speakers={0: ["Priya"], 1: ["Mayur"]},
    )  # fmt: skip
    ref = f"c:{chunks[0].id}"
    res = await search(user, "Who said that?", previous_result_ref=ref)
    assert res.status == "found"
    assert res.results[0].ref == ref
    assert res.results[0].speaker == "Priya"


async def test_other_user_results_never_returned(make_user):
    a, _ = await make_user()
    b, _ = await make_user()
    await seed(
        b, "Secret plan", date(2026, 10, 16), chunks=["Priya: We should use WebSockets for live updates."]
    )
    res = await search(a, "What did Priya say about WebSockets?")
    assert res.status == "no_reliable_memory"
    assert res.results == []


async def test_other_users_previous_ref_ignored(make_user):
    a, _ = await make_user()
    b, _ = await make_user()
    _, chunks, _ = await seed(b, "Secret plan", date(2026, 10, 16), chunks=["Priya: The secret code is 42."])
    res = await search(a, "Who said that?", previous_result_ref=f"c:{chunks[0].id}")
    assert all("secret" not in r.excerpt.lower() for r in res.results)


async def test_pending_and_failed_reported_not_found(make_user):
    user, _ = await make_user()
    await seed(
        user, "Still processing", date(2026, 10, 20), chunks=["We picked Render."], status="processing"
    )
    await seed(user, "Broken upload", date(2026, 10, 21), chunks=["We picked Fly."], status="failed")
    res = await search(user, "Which hosting did we pick?")
    assert res.status == "no_reliable_memory"
    assert res.results == []  # unprocessed conversations are never searched
    assert res.pending_conversations == ["Still processing"]
    assert res.failed_conversations == ["Broken upload"]
    assert "still processing" in res.guidance


async def test_embed_timeout_degraded_keyword_only(make_user):
    user, _ = await make_user()
    await seed(
        user, "API sync", date(2026, 10, 16),
        chunks=["Priya: We should use WebSockets for live updates."], speakers={0: ["Priya"]},
    )  # fmt: skip
    model = FakeModelClient()
    model.embed_timeout = True
    res = await search(user, "What did Priya say about WebSockets?", model=model)
    assert res.degraded is True
    assert res.status == "found"
    assert "keyword-only" in res.guidance


async def test_results_capped_and_excerpts_truncated(make_user):
    user, _ = await make_user()
    long = "Kubernetes " + "cluster sizing notes and more words " * 40
    await seed(user, "Infra", date(2026, 10, 16), chunks=[f"Kubernetes topic {i}. {long}" for i in range(9)])
    res = await search(user, "Kubernetes cluster sizing")
    s = get_settings()
    assert len(res.results) <= s.MAX_RESULTS
    assert all(len(r.excerpt) <= s.EXCERPT_MAX_CHARS + 1 for r in res.results)


async def test_timings_and_counts_present(make_user):
    user, _ = await make_user()
    await seed(user, "API sync", date(2026, 10, 16), chunks=["Priya: We should use WebSockets."],
               items=[{"topic": "transport", "statement": "Use WebSockets.", "quote": "We should use WebSockets.",
                       "state": "proposed"}])  # fmt: skip
    res = await search(user, "WebSockets")
    assert {"embed", "vector", "keyword", "fuse", "total"} <= set(res.timings_ms)
    assert res.conversation_count == 1
    assert res.memory_count == 1


async def test_source_context_returns_lines_and_rejects_other_user(make_user):
    a, _ = await make_user()
    b, _ = await make_user()
    _, chunks, _ = await seed(
        a, "API sync", date(2026, 10, 16), chunks=["Priya: Use WebSockets.", "Mayur: OK."]
    )
    async with get_sessionmaker()() as s:
        svc = RetrievalService(s, FakeModelClient())
        ctx = await svc.source_context(a.id, f"c:{chunks[0].id}")
        assert ctx.conversation_title == "API sync"
        assert any("WebSockets" in line["text"] for line in ctx.lines)
        with pytest.raises(NotFoundError):
            await svc.source_context(b.id, f"c:{chunks[0].id}")
        with pytest.raises(NotFoundError):
            await svc.source_context(a.id, "c:not-a-uuid")


async def test_search_route_requires_auth_and_scopes_to_user(client, make_user, login, monkeypatch):
    from app.integrations import model_client

    monkeypatch.setattr(model_client, "get_model_client", lambda: FakeModelClient())
    assert (await client.post("/api/v1/search", json={"question": "x"})).status_code == 401
    user, pw = await make_user()
    await seed(user, "API sync", date(2026, 10, 16), chunks=["Priya: We should use WebSockets."],
               speakers={0: ["Priya"]})  # fmt: skip
    await login(user, pw)
    resp = await client.post("/api/v1/search", json={"question": "What did Priya say about WebSockets?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "found"
    assert body["results"][0]["conversation_title"] == "API sync"


async def test_time_scoped_generic_question_lists_decisions_in_window(make_user, monkeypatch):
    # With a strict similarity floor, a question whose only content is a time window
    # ("what did we decide last week?") still returns the decisions inside that window.
    monkeypatch.setattr(get_settings(), "RETRIEVAL_MIN_VECTOR_SIM", 0.99)
    user, _ = await make_user()
    await seed(user, "Sprint review", date(2026, 10, 14), chunks=["Let's ship the export feature first."],
               items=[{"topic": "release order", "statement": "Ship the export feature first.",
                       "quote": "Let's ship the export feature first.", "state": "decided"}])  # fmt: skip
    await seed(user, "Old review", date(2026, 9, 2), chunks=["Let's ship billing first."],
               items=[{"topic": "release order", "statement": "Ship billing first.",
                       "quote": "Let's ship billing first.", "state": "decided"}])  # fmt: skip
    res = await search(user, "What did we decide last week?")
    assert res.status == "found"
    assert [r.conversation_title for r in res.results if r.kind == "decision"] == ["Sprint review"]


async def test_generic_question_without_window_still_abstains(make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "RETRIEVAL_MIN_VECTOR_SIM", 0.99)
    user, _ = await make_user()
    await seed(user, "Sprint review", date(2026, 10, 14), chunks=["Let's ship the export feature first."],
               items=[{"topic": "release order", "statement": "Ship the export feature first.",
                       "quote": "Let's ship the export feature first.", "state": "decided"}])  # fmt: skip
    res = await search(user, "What did we decide?")
    assert res.status == "no_reliable_memory"
