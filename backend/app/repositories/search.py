"""Raw retrieval queries. Every query is scoped to one user and to ready conversations."""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Hit:
    key: str  # "c:<uuid>" or "m:<uuid>"
    conversation_id: uuid.UUID
    score: float


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


def _window(d0: date | None, d1: date | None) -> tuple[str, dict[str, Any]]:
    if d0 and d1:
        return " AND v.conversation_date BETWEEN :d0 AND :d1", {"d0": d0, "d1": d1}
    return "", {}


_TABLES = {"c": ("chunks", "embedding"), "m": ("memory_items", "embedding")}


class SearchRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def vector(
        self, kind: str, user_id: uuid.UUID, qvec: list[float], d0: date | None, d1: date | None, k: int
    ) -> list[Hit]:
        table, col = _TABLES[kind]
        where, params = _window(d0, d1)
        await self.session.execute(text("SET LOCAL hnsw.ef_search = 100"))
        await self.session.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
        rows = await self.session.execute(
            text(
                f"SELECT t.id, t.conversation_id, 1 - (t.{col} <=> CAST(:q AS vector)) AS sim "
                f"FROM {table} t JOIN conversations v ON v.id = t.conversation_id "
                f"WHERE t.user_id = :uid AND v.user_id = :uid AND v.status = 'ready'{where} "
                f"ORDER BY t.{col} <=> CAST(:q AS vector) LIMIT :k"
            ),
            {"q": _vec(qvec), "uid": user_id, "k": k, **params},
        )
        return [Hit(f"{kind}:{r[0]}", r[1], float(r[2])) for r in rows]

    async def keyword(
        self, kind: str, user_id: uuid.UUID, tokens: list[str], d0: date | None, d1: date | None, k: int
    ) -> list[Hit]:
        if not tokens:
            return []
        table = _TABLES[kind][0]
        where, params = _window(d0, d1)
        rows = await self.session.execute(
            text(
                f"SELECT t.id, t.conversation_id, ts_rank_cd(t.search_tsv, query) AS rank "
                f"FROM {table} t JOIN conversations v ON v.id = t.conversation_id, "
                f"to_tsquery('english', :tsq) query "
                f"WHERE t.user_id = :uid AND v.user_id = :uid AND v.status = 'ready'{where} "
                f"AND t.search_tsv @@ query ORDER BY rank DESC LIMIT :k"
            ),
            {"tsq": " | ".join(tokens), "uid": user_id, "k": k, **params},
        )
        return [Hit(f"{kind}:{r[0]}", r[1], float(r[2])) for r in rows]

    async def names(
        self, kind: str, user_id: uuid.UUID, names: list[str], d0: date | None, d1: date | None, k: int
    ) -> list[Hit]:
        """Exact (word-boundary, case-insensitive) matches for names, acronyms and quoted phrases."""
        if not names:
            return []
        where, params = _window(d0, d1)
        terms: list[str] = []
        name_params: dict[str, Any] = {}
        for i, name in enumerate(names):
            name_params[f"n{i}"] = name
            pattern = f"'\\m' || :n{i} || '\\M'"
            if kind == "c":
                terms.append(
                    f"(CASE WHEN t.text ~* ({pattern}) OR :n{i} = ANY(t.speakers) THEN 1 ELSE 0 END)"
                )
            else:
                terms.append(
                    f"(CASE WHEN t.statement ~* ({pattern}) OR t.evidence_quote ~* ({pattern}) "
                    f"OR t.speaker = :n{i} OR t.owner = :n{i} THEN 1 ELSE 0 END)"
                )
        score = " + ".join(terms)
        table = _TABLES[kind][0]
        rows = await self.session.execute(
            text(
                f"SELECT t.id, t.conversation_id, ({score}) AS matched "
                f"FROM {table} t JOIN conversations v ON v.id = t.conversation_id "
                f"WHERE t.user_id = :uid AND v.user_id = :uid AND v.status = 'ready'{where} "
                f"AND ({score}) > 0 ORDER BY matched DESC, v.conversation_date DESC LIMIT :k"
            ),
            {"uid": user_id, "k": k, **params, **name_params},
        )
        return [Hit(f"{kind}:{r[0]}", r[1], float(r[2])) for r in rows]

    async def similarity(
        self, kind: str, user_id: uuid.UUID, ids: list[uuid.UUID], qvec: list[float]
    ) -> dict[str, float]:
        """Vector similarity of specific rows to the query (for rows found only by keyword)."""
        if not ids:
            return {}
        table, col = _TABLES[kind]
        rows = await self.session.execute(
            text(
                f"SELECT id, 1 - ({col} <=> CAST(:q AS vector)) FROM {table} "
                f"WHERE user_id = :uid AND id = ANY(:ids)"
            ),
            {"q": _vec(qvec), "uid": user_id, "ids": ids},
        )
        return {f"{kind}:{r[0]}": float(r[1]) for r in rows}

    async def conflicting_decisions(
        self, user_id: uuid.UUID, item_id: uuid.UUID, min_sim: float
    ) -> list[uuid.UUID]:
        rows = await self.session.execute(
            text(
                "SELECT m.id FROM memory_items m, memory_items s, conversations v "
                "WHERE s.id = :sid AND s.user_id = :uid AND m.user_id = :uid AND m.id <> s.id "
                "AND v.id = m.conversation_id AND v.status = 'ready' "
                "AND m.kind = 'decision' AND m.decision_state = 'decided' AND s.decision_state = 'decided' "
                "AND lower(m.statement) <> lower(s.statement) "
                "AND 1 - (m.topic_embedding <=> s.topic_embedding) >= :min_sim LIMIT 3"
            ),
            {"sid": item_id, "uid": user_id, "min_sim": min_sim},
        )
        return [r[0] for r in rows]
