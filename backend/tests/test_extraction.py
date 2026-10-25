import uuid
from datetime import date

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import Conversation, IngestionJob, MemoryItem
from app.services.extraction import locate_quote
from app.services.ingestion import IngestionService
from app.workers.ingestion_worker import process_job
from tests.fakes import FakeModelClient

TEXT = (
    "Priya: We should use WebSockets for live updates.\n"
    "Mayur: Agreed. Let's go with REST plus WebSockets.\n"
    "Mayur: I will write the auth spec by Friday.\n"
    "Priya: Maybe we try GraphQL later?"
)


def item(**kw):
    base = {
        "kind": "decision",
        "topic": "transport protocol",
        "statement": "Use REST plus WebSockets.",
        "speaker": "Mayur",
        "owner": None,
        "due_date": None,
        "decision_state": "decided",
        "change_signal": False,
        "evidence_quote": "Let's go with REST plus WebSockets.",
    }
    base.update(kw)
    return base


async def _ingest(user, model, self_speaker=None, text=TEXT):
    async with get_sessionmaker()() as s:
        conv = await IngestionService(s).create(
            user_id=user.id,
            title="API sync",
            conversation_date=date(2026, 10, 16),
            participants=["Priya", "Mayur"],
            self_speaker=self_speaker,
            text=text + f"\n{uuid.uuid4().hex}.",
            source_type="paste",
            filename=None,
        )
        await s.commit()
        job_id = await s.scalar(select(IngestionJob.id).where(IngestionJob.conversation_id == conv.id))
    await process_job(job_id, model)
    async with get_sessionmaker()() as s:
        items = (await s.scalars(select(MemoryItem).where(MemoryItem.conversation_id == conv.id))).all()
        job = await s.get(IngestionJob, job_id)
        conv = await s.get(Conversation, conv.id)
    return conv, items, job


def test_locate_quote_exact_and_normalized():
    original = "Mayur:  Let’s go with\nREST plus WebSockets."
    assert locate_quote(original, "go with\nREST") == (
        original.index("go with"),
        original.index("go with") + 12,
    )
    span = locate_quote(original, "Let's go with REST plus WebSockets.")
    assert span is not None
    assert original[span[0] : span[1]] == "Let’s go with\nREST plus WebSockets."
    assert locate_quote(original, "We chose GraphQL") is None
    assert locate_quote(original, "REST") is None  # too short to be evidence


async def test_item_with_exact_quote_kept_with_offsets(make_user):
    user, _ = await make_user()
    model = FakeModelClient()
    model.chat_responses.append({"items": [item()]})
    conv, items, job = await _ingest(user, model)
    assert conv.status == "ready"
    assert len(items) == 1
    it = items[0]
    assert conv.transcript_text[it.char_start : it.char_end] == "Let's go with REST plus WebSockets."
    assert it.decision_state == "decided"
    assert it.chunk_id is not None
    assert job.timings["extraction"]["kept"] == 1


async def test_item_with_paraphrased_quote_rejected(make_user):
    user, _ = await make_user()
    model = FakeModelClient()
    model.chat_responses.append({"items": [item(evidence_quote="Mayur agreed to use REST and WebSockets.")]})
    _, items, job = await _ingest(user, model)
    assert items == []
    assert job.timings["extraction"]["rejected_unlocated"] == 1


async def test_speaker_comes_from_labeled_source_not_model(make_user):
    user, _ = await make_user()
    model = FakeModelClient()
    # Model claims Priya said it; the transcript labels the line as Mayur's.
    model.chat_responses.append({"items": [item(speaker="Priya")]})
    _, items, job = await _ingest(user, model)
    assert items[0].speaker == "Mayur"
    assert job.timings["extraction"]["rejected_bad_speaker"] == 1


async def test_unlabeled_transcript_speaker_null(make_user):
    user, _ = await make_user()
    model = FakeModelClient()
    unlabeled = "We should use WebSockets. Let's go with REST plus WebSockets."
    model.chat_responses.append({"items": [item(speaker="Priya")]})
    _, items, _ = await _ingest(user, model, text=unlabeled)
    assert items[0].speaker is None


async def test_owner_is_user_only_when_self_speaker_set(make_user):
    user, _ = await make_user(name="Mayur")
    commitment = item(
        kind="commitment",
        topic="auth spec",
        statement="Mayur will write the auth spec by Friday.",
        owner="Mayur",
        decision_state=None,
        evidence_quote="I will write the auth spec by Friday.",
    )
    with_self = FakeModelClient()
    with_self.chat_responses.append({"items": [commitment]})
    _, items, _ = await _ingest(user, with_self, self_speaker="Mayur")
    assert items[0].owner == "Mayur" and items[0].owner_is_user is True

    without_self = FakeModelClient()
    without_self.chat_responses.append({"items": [commitment]})
    _, items, _ = await _ingest(user, without_self, self_speaker=None)
    assert items[0].owner == "Mayur" and items[0].owner_is_user is False


async def test_owner_not_grounded_is_dropped(make_user):
    user, _ = await make_user()
    model = FakeModelClient()
    model.chat_responses.append(
        {"items": [item(kind="commitment", owner="Rahul", decision_state=None,
                        evidence_quote="I will write the auth spec by Friday.")]}
    )  # fmt: skip
    _, items, _ = await _ingest(user, model)
    assert items[0].owner == "Mayur"  # "I" in Mayur's own line resolves to the labeled speaker


async def test_decision_state_required_for_decisions(make_user):
    user, _ = await make_user()
    model = FakeModelClient()
    model.chat_responses.append(
        {
            "items": [
                item(decision_state=None),
                item(
                    kind="fact",
                    decision_state="decided",
                    evidence_quote="We should use WebSockets for live updates.",
                ),
                item(decision_state="definitely", evidence_quote="Maybe we try GraphQL later?"),
            ]
        }
    )
    _, items, _ = await _ingest(user, model)
    by_quote = {i.evidence_quote: i for i in items}
    assert by_quote["Let's go with REST plus WebSockets."].decision_state == "unresolved"
    assert by_quote["We should use WebSockets for live updates."].decision_state is None
    assert by_quote["Maybe we try GraphQL later?"].decision_state == "unresolved"


async def test_long_transcript_windowed(make_user):
    user, _ = await make_user()
    filler = "\n".join(f"Priya: Filler sentence number {i} about nothing much at all." for i in range(400))
    long_text = TEXT + "\n" + filler
    model = FakeModelClient()
    model.chat_fn = lambda system, user_msg: {"items": [item()]}  # same item from every window
    _, items, _ = await _ingest(user, model, text=long_text)
    assert len(model.chat_calls) >= 2
    assert len(items) == 1  # deduped by (kind, normalized statement)


async def test_memory_items_embedded_with_doc_prefix(make_user):
    user, _ = await make_user()
    model = FakeModelClient()
    model.chat_responses.append({"items": [item()]})
    _, items, _ = await _ingest(user, model)
    doc_calls = [texts for texts, kind in model.embed_calls if kind == "document"]
    assert any(any("Use REST plus WebSockets." in t for t in texts) for texts in doc_calls)
    assert len(items[0].topic_embedding) == len(items[0].embedding)


async def test_extraction_failure_fails_conversation(make_user):
    from app.integrations.model_client import ModelError

    user, _ = await make_user()
    model = FakeModelClient()
    model.chat_responses.append(ModelError("chat endpoint returned 500"))
    conv, items, _ = await _ingest(user, model)
    assert conv.status == "failed"
    assert items == []
