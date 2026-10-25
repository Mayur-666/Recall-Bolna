import uuid
from datetime import date

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import Conversation, IngestionJob, MemoryItem
from app.services.ingestion import IngestionService
from app.workers.ingestion_worker import process_job
from tests.fakes import FakeModelClient

ECS_TEXT = "Asha: Let's go with AWS ECS for hosting.\nRavi: Agreed, ECS it is."
RENDER_TEXT = "Asha: We're dropping ECS and moving to Render.\nRavi: Fine, Render then."
DISCUSS_TEXT = "Asha: Render looks nice, maybe we decided too fast.\nRavi: Let's go with Render for the blog."


def decision(statement, quote, change=False):
    return {
        "kind": "decision",
        "topic": "deployment provider",
        "statement": statement,
        "speaker": "Asha",
        "owner": None,
        "due_date": None,
        "decision_state": "decided",
        "change_signal": change,
        "evidence_quote": quote,
    }


class Scenario:
    """A fake model whose extraction output depends on which transcript it sees."""

    def __init__(self, judge_answer=None):
        self.model = FakeModelClient()
        # Every decision about the deployment provider embeds identically -> same topic cluster.
        self.model.embed_key_fn = (
            lambda t: "deployment provider" if t.startswith("deployment provider") else t
        )
        self.judge_answer = judge_answer or {
            "relation": "replaces",
            "quote": "We're dropping ECS and moving to Render.",
        }
        self.judge_calls = 0
        self.model.chat_fn = self._chat

    def _chat(self, system, user_msg):
        if "relation" in system:
            self.judge_calls += 1
            return self.judge_answer
        if "AWS ECS" in user_msg:
            return {"items": [decision("Host on AWS ECS.", "Let's go with AWS ECS for hosting.")]}
        if "dropping ECS" in user_msg:
            return {
                "items": [
                    decision("Move hosting to Render.", "We're dropping ECS and moving to Render.", True)
                ]
            }
        if "for the blog" in user_msg:
            return {"items": [decision("Use Render for the blog.", "Let's go with Render for the blog.")]}
        return {"items": []}


async def ingest(user, text, day, model) -> uuid.UUID:
    async with get_sessionmaker()() as s:
        conv = await IngestionService(s).create(
            user_id=user.id,
            title=f"Deploy {day}",
            conversation_date=date(2026, 10, day),
            participants=["Asha", "Ravi"],
            self_speaker=None,
            text=text + f"\n{uuid.uuid4().hex}.",
            source_type="paste",
            filename=None,
        )
        await s.commit()
        job_id = await s.scalar(select(IngestionJob.id).where(IngestionJob.conversation_id == conv.id))
    await process_job(job_id, model)
    async with get_sessionmaker()() as s:
        assert (await s.get(Conversation, conv.id)).status == "ready"
    return conv.id


async def decisions(user):
    async with get_sessionmaker()() as s:
        rows = (await s.scalars(select(MemoryItem).where(MemoryItem.user_id == user.id))).all()
    return {r.statement: r for r in rows}


async def test_explicit_change_supersedes_earlier(make_user):
    user, _ = await make_user()
    sc = Scenario()
    await ingest(user, ECS_TEXT, 5, sc.model)
    await ingest(user, RENDER_TEXT, 12, sc.model)
    d = await decisions(user)
    assert d["Host on AWS ECS."].decision_state == "superseded"
    assert d["Host on AWS ECS."].superseded_by_id == d["Move hosting to Render."].id
    assert d["Move hosting to Render."].decision_state == "decided"


async def test_mere_discussion_does_not_supersede(make_user):
    user, _ = await make_user()
    sc = Scenario(judge_answer={"relation": "compatible", "quote": ""})
    await ingest(user, ECS_TEXT, 5, sc.model)
    await ingest(user, DISCUSS_TEXT, 12, sc.model)
    d = await decisions(user)
    assert d["Host on AWS ECS."].decision_state == "decided"
    assert d["Host on AWS ECS."].superseded_by_id is None
    assert d["Use Render for the blog."].decision_state == "decided"
    assert sc.judge_calls >= 1


async def test_out_of_order_ingest_relinks(make_user):
    user, _ = await make_user()
    sc = Scenario()
    await ingest(user, RENDER_TEXT, 12, sc.model)  # later-dated conversation arrives first
    await ingest(user, ECS_TEXT, 5, sc.model)
    d = await decisions(user)
    assert d["Host on AWS ECS."].decision_state == "superseded"
    assert d["Host on AWS ECS."].superseded_by_id == d["Move hosting to Render."].id
    assert d["Move hosting to Render."].decision_state == "decided"


async def test_delete_recomputes(make_user):
    user, _ = await make_user()
    sc = Scenario()
    await ingest(user, ECS_TEXT, 5, sc.model)
    render_conv = await ingest(user, RENDER_TEXT, 12, sc.model)
    async with get_sessionmaker()() as s:
        await IngestionService(s, sc.model).delete(user.id, render_conv)
        await s.commit()
    d = await decisions(user)
    assert list(d) == ["Host on AWS ECS."]
    assert d["Host on AWS ECS."].decision_state == "decided"
    assert d["Host on AWS ECS."].superseded_by_id is None


async def test_unlocatable_judge_quote_treated_as_no(make_user):
    user, _ = await make_user()
    sc = Scenario(judge_answer={"relation": "replaces", "quote": "We abandoned ECS completely last year."})
    await ingest(user, ECS_TEXT, 5, sc.model)
    await ingest(user, RENDER_TEXT, 12, sc.model)
    d = await decisions(user)
    assert d["Host on AWS ECS."].decision_state == "decided"


async def test_never_links_across_users(make_user):
    a, _ = await make_user()
    b, _ = await make_user()
    sc = Scenario()
    await ingest(a, ECS_TEXT, 5, sc.model)
    await ingest(b, RENDER_TEXT, 12, sc.model)
    assert (await decisions(a))["Host on AWS ECS."].decision_state == "decided"
    assert sc.judge_calls == 0


async def test_contradiction_marks_conflict_not_supersession(make_user):
    user, _ = await make_user()
    sc = Scenario(judge_answer={"relation": "contradicts", "quote": ""})
    await ingest(user, ECS_TEXT, 5, sc.model)
    await ingest(user, DISCUSS_TEXT, 12, sc.model)
    d = await decisions(user)
    assert d["Host on AWS ECS."].decision_state == "decided"
    assert d["Use Render for the blog."].decision_state == "decided"
    assert d["Use Render for the blog."].conflict_with_id == d["Host on AWS ECS."].id


async def test_compatible_decisions_not_conflicting(make_user):
    user, _ = await make_user()
    sc = Scenario(judge_answer={"relation": "compatible", "quote": ""})
    await ingest(user, ECS_TEXT, 5, sc.model)
    await ingest(user, DISCUSS_TEXT, 12, sc.model)
    d = await decisions(user)
    assert d["Use Render for the blog."].conflict_with_id is None
    assert d["Host on AWS ECS."].conflict_with_id is None


async def test_relink_clears_stale_conflicts(make_user):
    user, _ = await make_user()
    sc = Scenario(judge_answer={"relation": "contradicts", "quote": ""})
    await ingest(user, ECS_TEXT, 5, sc.model)
    blog = await ingest(user, DISCUSS_TEXT, 12, sc.model)
    async with get_sessionmaker()() as s:
        await IngestionService(s, sc.model).delete(user.id, blog)
        await s.commit()
    assert (await decisions(user))["Host on AWS ECS."].conflict_with_id is None
