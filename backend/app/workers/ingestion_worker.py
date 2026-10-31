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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from app.integrations.model_client import ModelClientProtocol, ModelError, get_model_client
from app.models import Chunk, Conversation, IngestionJob, MemoryItem, TranscriptSegment
from app.repositories.chunks import ChunksRepo, clear_derived
from app.repositories.jobs import JobsRepo
from app.services.chunker import ChunkDraft, build_chunks
from app.services.decision_linker import DecisionLinker
from app.services.events import get_memory_bus
from app.services.extraction import ExtractionService
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

    chunk_rows = [
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
    await ChunksRepo(session).add_all(chunk_rows)
    timings["chunks"] = len(drafts)
    timings["segments"] = len(segments)

    t = time.perf_counter()
    stats = await ExtractionService(session, model).extract_and_store(conv, segments, chunk_rows)
    timings["extract_ms"] = round((time.perf_counter() - t) * 1000, 1)
    timings["extraction"] = stats.as_dict()
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
        user_id, title = conv.user_id, conv.title
    bus = get_memory_bus()
    bus.publish(
        user_id,
        {"type": "conversation_processing", "conversation_id": str(job.conversation_id), "title": title},
    )

    started = time.perf_counter()
    try:
        async with sm() as session:
            conv = await session.get(Conversation, job.conversation_id)
            assert conv is not None
            linker = DecisionLinker(session, model)
            # On a retry, decisions elsewhere may have been linked to this conversation's old ones.
            old_ids = await linker.decision_ids_for_conversation(conv.user_id, conv.id)
            old_neighbors = [i for i in await linker.neighbor_ids(conv.user_id, old_ids) if i not in old_ids]
            await clear_derived(session, conv.user_id, conv.id)
            timings = await _build(session, conv, model)
            t_link = time.perf_counter()
            link = await linker.link_conversation(conv.user_id, conv.id, extra_ids=old_neighbors)
            timings["link_ms"] = round((time.perf_counter() - t_link) * 1000, 1)
            timings["linking"] = {
                "cluster": link.cluster,
                "judged": link.judged,
                "superseded": link.superseded,
            }
            conv.status = "ready"
            conv.error_message = None
            job_row = await session.get(IngestionJob, job_id)
            assert job_row is not None
            job_row.status = "done"
            job_row.finished_at = datetime.now(UTC)
            job_row.timings = {**timings, "total_ms": round((time.perf_counter() - started) * 1000, 1)}
            await session.commit()
            items = (
                await session.scalars(select(MemoryItem).where(MemoryItem.conversation_id == conv.id))
            ).all()
            bus.publish(
                user_id,
                {
                    "type": "conversation_ready",
                    "conversation_id": str(conv.id),
                    "title": title,
                    "source_type": conv.source_type,
                    "memories": [
                        {"id": str(m.id), "kind": m.kind, "statement": m.statement, "decision_state": m.decision_state}
                        for m in items
                    ],
                },
            )
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
        bus.publish(
            user_id,
            {
                "type": "conversation_failed",
                "conversation_id": str(job.conversation_id),
                "title": title,
                "error": _public_error(exc),
            },
        )


_wake: asyncio.Event | None = None


def wake_worker() -> None:
    """Start on a just-queued job now instead of at the next poll (call after the job is committed)."""
    if _wake is not None:
        _wake.set()


async def _sleep(stop: asyncio.Event, wake: asyncio.Event, timeout: float) -> None:
    if not wake.is_set():
        waiters = [asyncio.create_task(stop.wait()), asyncio.create_task(wake.wait())]
        try:
            await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for w in waiters:
                w.cancel()
    wake.clear()


async def run_worker(stop: asyncio.Event, poll_s: float = 1.0) -> None:
    global _wake
    _wake = wake = asyncio.Event()  # created here so it belongs to the running event loop
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
        await _sleep(stop, wake, poll_s)
