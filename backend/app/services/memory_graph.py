"""Data for the Memory Field visualisation: memories as nodes, topic clusters, and edges.

Clusters are connected components over topic-embedding similarity (the same signal the
decision linker uses); a cluster's label is its most common extracted topic, so no extra
model call is needed. Edges: "supersedes" and "conflicts" come from the linker's stored
links; "similar" joins memories whose content embeddings are very close.
"""

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Conversation, MemoryItem

MAX_NODES = 400
SIMILAR_EDGE_MIN = 0.82
MAX_SIMILAR_EDGES = 250


async def memory_graph(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(MemoryItem, Conversation.title, Conversation.conversation_date)
            .join(Conversation, Conversation.id == MemoryItem.conversation_id)
            .where(MemoryItem.user_id == user_id, Conversation.status == "ready")
            .order_by(Conversation.conversation_date.desc())
            .limit(MAX_NODES)
        )
    ).all()
    items = {r[0].id: r for r in rows}
    if not items:
        return {"nodes": [], "clusters": [], "edges": []}
    ids = list(items)

    pairs = await session.execute(
        text(
            "SELECT a.id, b.id, 1 - (a.topic_embedding <=> b.topic_embedding) AS topic_sim, "
            "1 - (a.embedding <=> b.embedding) AS sim "
            "FROM memory_items a JOIN memory_items b ON a.id < b.id "
            "WHERE a.user_id = :uid AND b.user_id = :uid AND a.id = ANY(:ids) AND b.id = ANY(:ids)"
        ),
        {"uid": user_id, "ids": ids},
    )
    link_min = get_settings().LINK_MIN_SIM
    parent = {i: i for i in ids}

    def find(x: uuid.UUID) -> uuid.UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    similar: list[tuple[uuid.UUID, uuid.UUID, float]] = []
    for a, b, topic_sim, sim in pairs:
        if topic_sim >= link_min:
            parent[find(a)] = find(b)
        if sim >= SIMILAR_EDGE_MIN:
            similar.append((a, b, float(sim)))

    groups: dict[uuid.UUID, list[uuid.UUID]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    clusters: list[dict[str, Any]] = []
    cluster_of: dict[uuid.UUID, int] = {}
    for members in sorted(groups.values(), key=len, reverse=True):
        if len(members) < 2:
            continue
        topics = Counter(items[m][0].topic for m in members)
        top = max(topics.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
        cid = len(clusters)
        clusters.append({"id": cid, "label": top, "size": len(members)})
        for m in members:
            cluster_of[m] = cid

    nodes = []
    for item, title, day in (items[i] for i in ids):
        nodes.append(
            {
                "id": f"m:{item.id}",
                "kind": item.kind,
                "statement": item.statement,
                "topic": item.topic,
                "decision_state": item.decision_state,
                "owner_is_user": item.owner_is_user,
                "speaker": item.speaker,
                "conversation_id": str(item.conversation_id),
                "conversation_title": title,
                "conversation_date": day.isoformat(),
                "chunk_ref": f"c:{item.chunk_id}" if item.chunk_id else None,
                "cluster": cluster_of.get(item.id),
            }
        )

    edges: list[dict[str, Any]] = []
    linked: set[frozenset[uuid.UUID]] = set()
    for item, _, _ in items.values():
        if item.superseded_by_id in items:
            edges.append(
                {"a": f"m:{item.id}", "b": f"m:{item.superseded_by_id}", "type": "supersedes", "weight": 1.0}
            )
            linked.add(frozenset((item.id, item.superseded_by_id)))
        if item.conflict_with_id in items:
            edges.append(
                {"a": f"m:{item.id}", "b": f"m:{item.conflict_with_id}", "type": "conflicts", "weight": 1.0}
            )
            linked.add(frozenset((item.id, item.conflict_with_id)))
    for a, b, sim in sorted(similar, key=lambda t: -t[2])[:MAX_SIMILAR_EDGES]:
        if frozenset((a, b)) not in linked:
            edges.append({"a": f"m:{a}", "b": f"m:{b}", "type": "similar", "weight": round(sim, 3)})
    return {"nodes": nodes, "clusters": clusters, "edges": edges}
