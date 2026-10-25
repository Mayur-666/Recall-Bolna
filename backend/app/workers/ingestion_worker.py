"""Background ingestion: segment -> chunk -> embed -> (extract -> link) -> ready.

Jobs live in Postgres (ingestion_jobs) and are claimed with SKIP LOCKED, so the
queue survives restarts and needs no extra infrastructure.
"""

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from app.integrations.model_client import ModelClientProtocol, ModelError, get_model_client
from app.models import Chunk, Conversation, IngestionJob, TranscriptSegment
from app.repositories.chunks import ChunksRepo, clear_derived
from app.repositories.jobs import JobsRepo
from app.services.chunker import ChunkDraft, build_chunks
from app.services.transcript_parser import parse_transcript

log = logging.getLogger(__name__)
EMBED_BATCH = 32


def embed_text_for(conv: Conversation, chunk: ChunkDraft) -> str:
    speakers = ", ".join(chunk.speakers) or "unknown"
    return f"[{conv.title} · {conv.conversation_date:%Y-%m-%d} · speakers: {speakers}] {chunk.text}"


async def _build(session: AsyncSession, conv: Conversation, model: ModelClientProtocol) -> dict[str, Any]:
    timings: dict[str, Any] = {}
    t = time.perf_counter()
    segments = parse_transcript(conv.transcript_text, conv.original_filename, conv.participants or None)
    drafts = build_chunks(segments, conv.transcript_text)
    timings["parse_ms"] = round((time.perf_counter() - t) * 1000, 1)
    if not drafts:
        raise ModelError("transcript has no usable text")  # surfaced as a failed conversation

    session.add_all(
        TranscriptSegment(
            conversation_id=conv.id,
            user_id=conv.user_id,
            seq=s.seq,
            speaker=s.speaker,
            text=s.text,
            char_start=s.char_start,
            char_end=s.char_end,
        )
        for s in segments
    )

    t = time.perf_counter()
    texts = [embed_text_for(conv, d) for d in drafts]
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        vectors.extend(await model.embed(texts[i : i + EMBED_BATCH], kind="document"))
    timings["embed_ms"] = round((time.perf_counter() - t) * 1000, 1)

    await ChunksRepo(session).add_all(
        [
            Chunk(
                conversation_id=conv.id,
                user_id=conv.user_id,
                seq=d.seq,
                text=d.text,
                char_start=d.char_start,
                char_end=d.char_end,
                speakers=d.speakers,
                embed_text=text,
                embedding=vec,
            )
            for d, text, vec in zip(drafts, texts, vectors, strict=True)
        ]
    )
    timings["chunks"] = len(drafts)
    timings["segments"] = len(segments)
    return timings


def _public_error(exc: Exception) -> str:
    if isinstance(exc, ModelError):
        return f"Embedding/extraction service failed: {exc}"[:480]
    return "Processing failed due to an internal error. Retry, or check the server logs."


async def process_job(job_id: uuid.UUID, model: ModelClientProtocol | None = None) -> None:
    model = model or get_model_client()
    sm = get_sessionmaker()

    async with sm() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            return
        conv = await session.get(Conversation, job.conversation_id)
        if conv is None or conv.user_id != job.user_id:
            job.status = "failed"
            job.last_error = "conversation missing"
            await session.commit()
            return
        conv.status = "processing"
        conv.attempts += 1
        job.status = "running"
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        await session.commit()

    started = time.perf_counter()
    try:
        async with sm() as session:
            conv = await session.get(Conversation, job.conversation_id)
            assert conv is not None
            await clear_derived(session, conv.user_id, conv.id)
            timings = await _build(session, conv, model)
            conv.status = "ready"
            conv.error_message = None
            job_row = await session.get(IngestionJob, job_id)
            assert job_row is not None
            job_row.status = "done"
            job_row.finished_at = datetime.now(UTC)
            job_row.timings = {**timings, "total_ms": round((time.perf_counter() - started) * 1000, 1)}
            await session.commit()
    except Exception as exc:
        log.warning("ingestion job %s failed: %s", job_id, type(exc).__name__)
        async with sm() as session:
            conv = await session.get(Conversation, job.conversation_id)
            job_row = await session.get(IngestionJob, job_id)
            if conv is not None:
                conv.status = "failed"
                conv.error_message = _public_error(exc)
            if job_row is not None:
                job_row.status = "failed"
                job_row.last_error = _public_error(exc)
                job_row.finished_at = datetime.now(UTC)
            await session.commit()


async def run_worker(stop: asyncio.Event, poll_s: float = 1.0) -> None:
    sm = get_sessionmaker()
    while not stop.is_set():
        job_id: uuid.UUID | None = None
        try:
            async with sm() as session:
                job = await JobsRepo(session).claim_next()
                if job is not None:
                    job_id = job.id
                    await session.commit()
            if job_id is not None:
                await process_job(job_id)
                continue
        except Exception:
            log.exception("worker loop error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_s)
        except TimeoutError:
            pass
