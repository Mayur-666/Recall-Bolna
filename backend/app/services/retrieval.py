"""Hybrid memory search: vector + full-text + exact names, fused with reciprocal rank fusion,
then gated so Recall abstains instead of returning a weak match as an answer.

The voice agent's LLM writes the spoken answer from this output, so the output carries
evidence (conversation, date, speaker, excerpt), decision state, and a guidance string
built only from fixed templates, never from transcript text.
"""

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.integrations.model_client import ModelClientProtocol, ModelError
from app.models import Chunk, Conversation, MemoryItem, TranscriptSegment
from app.repositories.conversations import ConversationsRepo
from app.repositories.search import Hit, SearchRepo
from app.schemas.search import Evidence, SearchQuery, SearchResult, SourceContext
from app.services.dates import humanize, parse_relative_range

__all__ = ["RetrievalService", "SearchQuery"]

# Words that say "this is a question about memory" rather than what it is about.
GENERIC = {
    "what", "who", "whom", "when", "where", "why", "how", "which", "did", "do", "does", "done", "was", "were",
    "is", "are", "am", "be", "been", "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "about",
    "with", "we", "i", "you", "they", "he", "she", "it", "our", "my", "me", "us", "that", "this", "these",
    "those", "there", "any", "anything", "something", "decide", "decided", "decision", "decisions", "say",
    "said", "says", "tell", "told", "talk", "talked", "discuss", "discussed", "agree", "agreed", "promise",
    "promised", "mention", "mentioned", "remember", "recall", "think", "thought", "plan", "planned", "pick",
    "picked", "choose", "chose", "chosen", "select", "selected", "finalize", "finalized", "actually", "last",
    "week", "month", "yesterday", "today", "ago", "days", "day", "again", "please", "can", "could", "would",
    "should", "will", "up", "follow", "get", "got", "go", "going", "have", "had", "has", "from", "at",
}  # fmt: skip
_TOKEN = re.compile(r"[A-Za-z0-9]+")
_NAME = re.compile(r"\b([A-Z][a-zA-Z0-9]+|[A-Z0-9]{2,})\b")
_QUOTED = re.compile(r"[\"“]([^\"”]{3,60})[\"”]")
_SAFE_PHRASE = re.compile(r"[^A-Za-z0-9 '\-]")

PREV_REF_WEIGHT = 2.0
SUPERSEDED_SUFFIX = "superseded"

G_FOUND = "Answer only from these results. Say which conversation it came from and when."
G_SUPERSEDED = "A decision in these results was later changed; give the newer decision and say it changed."
G_CONFLICT = (
    "Two decisions on this topic disagree and neither explicitly replaces the other; "
    "present both with their dates and ask which one applies."
)
G_AMBIGUOUS = (
    "These results come from different conversations; ask which conversation they mean before answering."
)
G_NO_MEMORY = (
    "No reliable memory. Say you don't have a reliable memory of that; "
    "mention the closest result only as a weak match, if at all."
)
G_PENDING = (
    "Some conversations are still processing or failed to process, so the answer may be in one of those."
)
G_DEGRADED = "Search ran in keyword-only mode because the embedding service was slow or unavailable."


def content_tokens(text: str) -> list[str]:
    out = [t.lower() for t in _TOKEN.findall(text) if t.lower() not in GENERIC and len(t) > 1]
    return list(dict.fromkeys(out))


def name_terms(text: str) -> list[str]:
    names = [n for n in _NAME.findall(text) if n.lower() not in GENERIC]
    phrases = [_SAFE_PHRASE.sub("", p).strip() for p in _QUOTED.findall(text)]
    return list(dict.fromkeys([*names, *(p for p in phrases if p)]))[:6]


def _stem(token: str) -> str:
    return token[: max(4, len(token) - 2)] if len(token) > 4 else token


def coverage(tokens: list[str], text: str) -> float:
    if not tokens:
        return 0.0
    low = text.lower()
    return sum(1 for t in tokens if _stem(t) in low) / len(tokens)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def parse_ref(ref: str | None) -> tuple[str, uuid.UUID] | None:
    if not ref or len(ref) < 3 or ref[1] != ":" or ref[0] not in "cm":
        return None
    try:
        return ref[0], uuid.UUID(ref[2:])
    except ValueError:
        return None


@dataclass
class _Cand:
    key: str
    conversation_id: uuid.UUID
    fused: float = 0.0
    vec_sim: float | None = None
    in_keyword: bool = False
    in_name: bool = False
    is_prev: bool = False
    lists: set[str] = field(default_factory=set)


class RetrievalService:
    def __init__(self, session: AsyncSession, model: ModelClientProtocol) -> None:
        self.session = session
        self.model = model
        self.repo = SearchRepo(session)
        self.settings = get_settings()

    # ------------------------------------------------------------------ search
    async def search(self, user_id: uuid.UUID, q: SearchQuery, today: date) -> SearchResult:
        s = self.settings
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        query = (q.standalone_query or q.question).strip()
        both = f"{q.question} {q.standalone_query or ''}"
        window = (q.from_date, q.to_date) if q.from_date and q.to_date else parse_relative_range(both, today)
        d0, d1 = window if window else (None, None)
        tokens = content_tokens(query)
        names = name_terms(both)
        name_lower = {n.lower() for n in names}
        topic_tokens = [t for t in tokens if t not in name_lower]
        k = s.CANDIDATES_PER_LIST

        async def embed() -> list[float] | None:
            te = time.perf_counter()
            try:
                [vec] = await self.model.embed([query], kind="query", timeout_s=s.EMBED_TIMEOUT_S)
                return vec
            except ModelError:  # includes EmbeddingTimeout
                return None
            finally:
                timings["embed"] = round((time.perf_counter() - te) * 1000, 1)

        async def lexical() -> dict[str, list[Hit]]:
            tk = time.perf_counter()
            out = {
                "kw_c": await self.repo.keyword("c", user_id, tokens, d0, d1, k),
                "kw_m": await self.repo.keyword("m", user_id, tokens, d0, d1, k),
                "name_c": await self.repo.names("c", user_id, names, d0, d1, k),
                "name_m": await self.repo.names("m", user_id, names, d0, d1, k),
            }
            timings["keyword"] = round((time.perf_counter() - tk) * 1000, 1)
            return out

        qvec, lists = await asyncio.gather(embed(), lexical())
        degraded = qvec is None
        tv = time.perf_counter()
        if qvec is not None:
            lists["vec_c"] = await self.repo.vector("c", user_id, qvec, d0, d1, k)
            lists["vec_m"] = await self.repo.vector("m", user_id, qvec, d0, d1, k)
        timings["vector"] = round((time.perf_counter() - tv) * 1000, 1)

        tf = time.perf_counter()
        prev = await self._prev_ref_hits(user_id, q.previous_result_ref)
        cands = self._fuse(lists, prev)
        if qvec is not None:
            await self._fill_similarity(user_id, cands, qvec)
        texts = await self._coverage_texts(user_id, list(cands))
        passing = [
            c
            for c in sorted(cands.values(), key=lambda c: -c.fused)
            if self._passes(c, texts, topic_tokens, names, degraded)
        ]
        timings["fuse"] = round((time.perf_counter() - tf) * 1000, 1)

        counts = await self._counts(user_id)
        status_titles = await ConversationsRepo(self.session).titles_by_status(
            user_id, ("queued", "processing", "failed")
        )
        pending = status_titles["queued"] + status_titles["processing"]
        failed = status_titles["failed"]

        guidance: list[str] = []
        if passing:
            evidence = await self._evidence(user_id, [c.key for c in passing[: s.MAX_RESULTS]], cands, today)
            evidence = await self._add_decision_partners(user_id, evidence, today)
            evidence = evidence[: s.MAX_RESULTS]
            status = "found"
            guidance.append(G_FOUND)
            if any(e.conflict for e in evidence):
                guidance.append(G_CONFLICT)
            elif self._ambiguous(passing, evidence, query):
                status = "ambiguous"
                guidance = [G_AMBIGUOUS]
            if any(e.decision_state == SUPERSEDED_SUFFIX for e in evidence):
                guidance.append(G_SUPERSEDED)
        else:
            status = "no_reliable_memory"
            best = sorted(cands.values(), key=lambda c: -c.fused)[:1]
            evidence = await self._evidence(user_id, [c.key for c in best], cands, today)
            for e in evidence:
                e.weak = True
            guidance.append(G_NO_MEMORY)
            if pending or failed:
                guidance.append(G_PENDING)
        if degraded:
            guidance.append(G_DEGRADED)

        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return SearchResult(
            status=status,
            results=evidence,
            memory_count=counts[1],
            conversation_count=counts[0],
            pending_conversations=pending,
            failed_conversations=failed,
            guidance=" ".join(guidance),
            timings_ms=timings,
            degraded=degraded,
        )

    # ------------------------------------------------------------------ helpers
    def _fuse(self, lists: dict[str, list[Hit]], prev: list[Hit]) -> dict[str, _Cand]:
        k = self.settings.RRF_K
        cands: dict[str, _Cand] = {}
        named = {**lists, "prev": prev}
        for name, hits in named.items():
            weight = PREV_REF_WEIGHT if name == "prev" else 1.0
            for rank, hit in enumerate(hits, start=1):
                c = cands.setdefault(hit.key, _Cand(hit.key, hit.conversation_id))
                c.fused += weight / (k + rank)
                c.lists.add(name)
                if name.startswith("vec"):
                    c.vec_sim = max(c.vec_sim or -1.0, hit.score)
                elif name.startswith("kw"):
                    c.in_keyword = True
                elif name.startswith("name"):
                    c.in_name = True
                elif name == "prev":
                    c.is_prev = True
        return cands

    async def _fill_similarity(self, user_id: uuid.UUID, cands: dict[str, _Cand], qvec: list[float]) -> None:
        for kind in ("c", "m"):
            missing = [uuid.UUID(c.key[2:]) for c in cands.values() if c.key[0] == kind and c.vec_sim is None]
            sims = await self.repo.similarity(kind, user_id, missing, qvec)
            for key, sim in sims.items():
                cands[key].vec_sim = sim

    def _passes(
        self, c: _Cand, texts: dict[str, str], topic_tokens: list[str], names: list[str], degraded: bool
    ) -> bool:
        if c.is_prev:
            return True
        min_sim = self.settings.RETRIEVAL_MIN_VECTOR_SIM
        cov = coverage(topic_tokens, texts.get(c.key, ""))
        needed = 1.0 if len(topic_tokens) <= 2 else 0.67
        lexical_ok = bool(topic_tokens) and cov >= needed
        if c.vec_sim is not None and c.vec_sim >= min_sim:
            return True
        if lexical_ok and (c.in_keyword or c.in_name):
            return True
        if c.in_name and not topic_tokens:
            return True
        return False

    async def _coverage_texts(self, user_id: uuid.UUID, keys: list[str]) -> dict[str, str]:
        chunk_ids = [uuid.UUID(k[2:]) for k in keys if k[0] == "c"]
        item_ids = [uuid.UUID(k[2:]) for k in keys if k[0] == "m"]
        out: dict[str, str] = {}
        if chunk_ids:
            rows = await self.session.execute(
                select(Chunk.id, Chunk.text, Conversation.title)
                .join(Conversation, Conversation.id == Chunk.conversation_id)
                .where(Chunk.user_id == user_id, Chunk.id.in_(chunk_ids))
            )
            out.update({f"c:{r[0]}": f"{r[2]} {r[1]}" for r in rows})
        if item_ids:
            rows = await self.session.execute(
                select(
                    MemoryItem.id, MemoryItem.topic, MemoryItem.statement, MemoryItem.evidence_quote
                ).where(MemoryItem.user_id == user_id, MemoryItem.id.in_(item_ids))
            )
            out.update({f"m:{r[0]}": f"{r[1]} {r[2]} {r[3]}" for r in rows})
        return out

    async def _prev_ref_hits(self, user_id: uuid.UUID, ref: str | None) -> list[Hit]:
        parsed = parse_ref(ref)
        if parsed is None:
            return []
        kind, rid = parsed
        model: Any = Chunk if kind == "c" else MemoryItem
        row = await self.session.scalar(
            select(model)
            .join(Conversation, Conversation.id == model.conversation_id)
            .where(model.id == rid, model.user_id == user_id, Conversation.status == "ready")
        )
        if row is None:
            return []  # unknown or another user's ref: ignored, never an error that leaks existence
        return [Hit(f"{kind}:{rid}", row.conversation_id, 1.0)]

    async def _counts(self, user_id: uuid.UUID) -> tuple[int, int]:
        conversations = await ConversationsRepo(self.session).count_ready(user_id)
        memories = await self.session.scalar(
            select(func.count())
            .select_from(MemoryItem)
            .join(Conversation, Conversation.id == MemoryItem.conversation_id)
            .where(MemoryItem.user_id == user_id, Conversation.status == "ready")
        )
        return conversations, int(memories or 0)

    async def _evidence(
        self, user_id: uuid.UUID, keys: list[str], cands: dict[str, _Cand], today: date
    ) -> list[Evidence]:
        limit = self.settings.EXCERPT_MAX_CHARS
        out: list[Evidence] = []
        for key in keys:
            kind, rid = key[0], uuid.UUID(key[2:])
            score = round(cands[key].fused, 5) if key in cands else 0.0
            if kind == "c":
                row = (
                    await self.session.execute(
                        select(Chunk, Conversation)
                        .join(Conversation, Conversation.id == Chunk.conversation_id)
                        .where(Chunk.id == rid, Chunk.user_id == user_id)
                    )
                ).first()
                if row is None:
                    continue
                chunk, conv = row
                out.append(
                    Evidence(
                        ref=key,
                        kind="chunk",
                        conversation_id=conv.id,
                        conversation_title=conv.title,
                        conversation_date=conv.conversation_date,
                        relative_date=humanize(conv.conversation_date, today),
                        speaker=", ".join(chunk.speakers) if chunk.speakers else None,
                        excerpt=truncate(chunk.text, limit),
                        score=score,
                    )
                )
            else:
                ev = await self._item_evidence(user_id, rid, today, score)
                if ev is not None:
                    out.append(ev)
        return out

    async def _item_evidence(
        self, user_id: uuid.UUID, rid: uuid.UUID, today: date, score: float
    ) -> Evidence | None:
        row = (
            await self.session.execute(
                select(MemoryItem, Conversation)
                .join(Conversation, Conversation.id == MemoryItem.conversation_id)
                .where(MemoryItem.id == rid, MemoryItem.user_id == user_id, Conversation.status == "ready")
            )
        ).first()
        if row is None:
            return None
        item, conv = row
        return Evidence(
            ref=f"m:{item.id}",
            kind=item.kind,
            conversation_id=conv.id,
            conversation_title=conv.title,
            conversation_date=conv.conversation_date,
            relative_date=humanize(conv.conversation_date, today),
            speaker=item.speaker,
            statement=item.statement,
            excerpt=truncate(item.evidence_quote, self.settings.EXCERPT_MAX_CHARS),
            decision_state=item.decision_state,
            superseded_by_ref=f"m:{item.superseded_by_id}" if item.superseded_by_id else None,
            owner=item.owner,
            owner_is_user=item.owner_is_user,
            due_date=item.due_date,
            score=score,
        )

    async def _add_decision_partners(
        self, user_id: uuid.UUID, evidence: list[Evidence], today: date
    ) -> list[Evidence]:
        """Pull in the decision that superseded a result, and any unresolved conflicting decision."""
        out = list(evidence)
        present = {e.ref for e in out}
        i = 0
        while i < len(out):
            e = out[i]
            partners: list[str] = []
            if e.superseded_by_ref:
                partners.append(e.superseded_by_ref)
            if e.kind == "decision" and e.decision_state == "decided":
                ids = await self.repo.conflicting_decisions(
                    user_id, uuid.UUID(e.ref[2:]), self.settings.LINK_MIN_SIM
                )
                if ids:
                    e.conflict = True
                    partners.extend(f"m:{pid}" for pid in ids)
            insert_at = i + 1
            for ref in partners:
                if ref in present:
                    if ref != e.superseded_by_ref:
                        for other in out:
                            if other.ref == ref:
                                other.conflict = True
                    continue
                ev = await self._item_evidence(user_id, uuid.UUID(ref[2:]), today, 0.0)
                if ev is None:
                    continue
                if ref != e.superseded_by_ref:
                    ev.conflict = True
                out.insert(insert_at, ev)
                present.add(ref)
                insert_at += 1
            i += 1
        return out

    def _ambiguous(self, passing: list[_Cand], evidence: list[Evidence], query: str) -> bool:
        if len(passing) < 2 or passing[0].is_prev:
            return False
        a, b = passing[0], passing[1]
        if a.conversation_id == b.conversation_id:
            return False
        if a.fused > 0 and (a.fused - b.fused) / a.fused > self.settings.AMBIGUITY_MARGIN:
            return False
        if any(e.superseded_by_ref or e.decision_state == SUPERSEDED_SUFFIX for e in evidence):
            return False
        q_tokens = set(content_tokens(query))
        for e in evidence[:2]:
            if q_tokens & set(content_tokens(e.conversation_title)):
                return False
        return True

    # ------------------------------------------------------------------ context
    async def source_context(self, user_id: uuid.UUID, ref: str, window: int = 3) -> SourceContext:
        parsed = parse_ref(ref)
        if parsed is None:
            raise NotFoundError("Source not found.")
        kind, rid = parsed
        model: Any = Chunk if kind == "c" else MemoryItem
        row = (
            await self.session.execute(
                select(model.char_start, model.char_end, Conversation)
                .join(Conversation, Conversation.id == model.conversation_id)
                .where(model.id == rid, model.user_id == user_id, Conversation.status == "ready")
            )
        ).first()
        if row is None:
            raise NotFoundError("Source not found.")
        start, end, conv = row
        segs = (
            await self.session.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.user_id == user_id, TranscriptSegment.conversation_id == conv.id)
                .order_by(TranscriptSegment.seq)
            )
        ).all()
        hit = [i for i, sg in enumerate(segs) if sg.char_end > start and sg.char_start < end]
        if hit:
            lo, hi = max(0, hit[0] - window), min(len(segs), hit[-1] + window + 1)
            lines = [{"speaker": sg.speaker, "text": truncate(sg.text, 400)} for sg in segs[lo:hi]]
        else:  # no segments stored (e.g. seeded directly): fall back to the raw span
            lines = [{"speaker": None, "text": truncate(conv.transcript_text[start:end], 400)}]
        return SourceContext(
            ref=ref, conversation_title=conv.title, conversation_date=conv.conversation_date, lines=lines[:12]
        )
