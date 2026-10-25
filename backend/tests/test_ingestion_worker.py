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
