import uuid
from datetime import date

from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.integrations.model_client import ModelError
from app.models import Chunk, Conversation, IngestionJob, TranscriptSegment
from app.repositories.jobs import JobsRepo
from app.services.ingestion import IngestionService
from app.workers.ingestion_worker import process_job
from tests.fakes import FakeModelClient

TEXT = (
    "Priya: We need live updates. WebSockets are the obvious choice. Polling is wasteful.\n"
    "Mayur: Agreed on WebSockets. Let's go with REST plus WebSockets."
)


async def _new_conversation(user, text=TEXT) -> tuple[uuid.UUID, uuid.UUID]:
    async with get_sessionmaker()() as s:
        conv = await IngestionService(s).create(
            user_id=user.id,
            title="API sync",
            conversation_date=date(2026, 10, 16),
            participants=["Priya", "Mayur"],
            self_speaker=None,
            text=text + f"\n{uuid.uuid4().hex}.",
            source_type="paste",
            filename=None,
        )
        await s.commit()
        job_id = await s.scalar(select(IngestionJob.id).where(IngestionJob.conversation_id == conv.id))
        return conv.id, job_id


async def _counts(conv_id):
    async with get_sessionmaker()() as s:
        conv = await s.get(Conversation, conv_id)
        n_chunks = await s.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.conversation_id == conv_id)
        )
        n_segs = await s.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.conversation_id == conv_id)
        )
        return conv, n_chunks, n_segs


async def test_job_moves_conversation_to_ready_with_chunks_and_segments(make_user):
    user, _ = await make_user()
    conv_id, job_id = await _new_conversation(user)
    model = FakeModelClient()

    await process_job(job_id, model)

    conv, n_chunks, n_segs = await _counts(conv_id)
    assert conv.status == "ready"
    assert conv.attempts == 1
    assert n_segs == 3  # two labeled lines + the unique marker line
    assert n_chunks >= 2
    texts, kind = model.embed_calls[0]
    assert kind == "document"
    assert texts[0].startswith("[API sync · 2026-10-16 · speakers: Priya, Mayur] ")
    async with get_sessionmaker()() as s:
        job = await s.get(IngestionJob, job_id)
        assert job.status == "done"
        assert "embed_ms" in job.timings


async def test_model_error_marks_failed_with_message_and_attempts(make_user):
    user, _ = await make_user()
    conv_id, job_id = await _new_conversation(user)
    model = FakeModelClient()
    model.embed_fail = ModelError("embedding endpoint returned 500")

    await process_job(job_id, model)

    conv, n_chunks, n_segs = await _counts(conv_id)
    assert conv.status == "failed"
    assert conv.attempts == 1
    assert "embedding" in conv.error_message.lower()
    assert "WebSockets" not in conv.error_message  # never leak transcript text
    assert n_chunks == 0 and n_segs == 0  # no partial rows


async def test_retry_after_failure_succeeds(make_user):
    user, _ = await make_user()
    conv_id, job_id = await _new_conversation(user)
    failing = FakeModelClient()
    failing.embed_fail = ModelError("down")
    await process_job(job_id, failing)

    async with get_sessionmaker()() as s:
        await IngestionService(s).retry(user.id, conv_id)
        await s.commit()
        retry_job = await s.scalar(
            select(IngestionJob.id).where(
                IngestionJob.conversation_id == conv_id, IngestionJob.status == "queued"
            )
        )

    await process_job(retry_job, FakeModelClient())
    conv, n_chunks, _ = await _counts(conv_id)
    assert conv.status == "ready"
    assert conv.attempts == 2
    assert conv.error_message is None
    assert n_chunks >= 2


async def test_two_workers_dont_double_claim(make_user):
    user, _ = await make_user()
    await _new_conversation(user)
    await _new_conversation(user)
    sm = get_sessionmaker()
    async with sm() as a, sm() as b:
        job_a = await JobsRepo(a).claim_next()
        job_b = await JobsRepo(b).claim_next()
        assert job_a is not None and job_b is not None
        assert job_a.id != job_b.id
        await a.rollback()
        await b.rollback()


async def _collect(user_id, until_type, out):
    from app.services.events import get_memory_bus

    async for event in get_memory_bus().subscribe(user_id):
        out.append(event)
        if event["type"] == until_type:
            return


async def test_worker_publishes_live_memory_events_to_the_owner_only(make_user):
    import asyncio

    user, _ = await make_user()
    other, _ = await make_user()
    conv_id, job_id = await _new_conversation(user)
    mine, theirs = [], []
    task = asyncio.create_task(_collect(user.id, "conversation_ready", mine))
    spy = asyncio.create_task(_collect(other.id, "conversation_ready", theirs))
    await asyncio.sleep(0.05)

    await process_job(job_id, FakeModelClient())
    await asyncio.wait_for(task, timeout=2)
    spy.cancel()

    assert [e["type"] for e in mine] == ["conversation_processing", "conversation_ready"]
    ready = mine[-1]
    assert ready["conversation_id"] == str(conv_id) and ready["title"] == "API sync"
    assert ready["source_type"] == "paste"
    assert isinstance(ready["memories"], list)
    assert all({"id", "kind", "statement"} <= set(m) for m in ready["memories"])
    assert theirs == []


async def test_worker_publishes_failure_event(make_user):
    import asyncio

    user, _ = await make_user()
    _, job_id = await _new_conversation(user)
    events = []
    task = asyncio.create_task(_collect(user.id, "conversation_failed", events))
    await asyncio.sleep(0.05)
    model = FakeModelClient()
    model.embed_fail = ModelError("embedding endpoint returned 500")
    await process_job(job_id, model)
    await asyncio.wait_for(task, timeout=2)
    assert events[-1]["type"] == "conversation_failed" and events[-1]["error"]


async def test_wake_worker_starts_a_queued_job_without_waiting_for_the_poll(make_user, monkeypatch):
    import asyncio
    import time

    from app.integrations import model_client
    from app.workers import ingestion_worker

    monkeypatch.setattr(model_client, "get_model_client", lambda: FakeModelClient())
    monkeypatch.setattr(ingestion_worker, "get_model_client", lambda: FakeModelClient())
    user, _ = await make_user()
    stop = asyncio.Event()
    worker = asyncio.create_task(ingestion_worker.run_worker(stop, poll_s=30))  # a poll would take 30 s
    await asyncio.sleep(0.2)  # worker finds nothing and goes to sleep
    conv_id, _ = await _new_conversation(user)
    started = time.perf_counter()
    ingestion_worker.wake_worker()
    try:
        for _ in range(100):
            async with get_sessionmaker()() as s:
                if (await s.get(Conversation, conv_id)).status == "ready":
                    break
            await asyncio.sleep(0.05)
        assert (await _counts(conv_id))[0].status == "ready"
        assert time.perf_counter() - started < 5
    finally:
        stop.set()
        await asyncio.wait_for(worker, timeout=5)
