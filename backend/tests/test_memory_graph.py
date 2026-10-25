from datetime import date

from app.db.session import get_sessionmaker
from app.models import MemoryItem
from tests.test_retrieval import seed


async def test_graph_clusters_edges_and_isolation(client, make_user, login):
    user, pw = await make_user()
    other, _ = await make_user()
    _, chunks, (ecs, ecs_twin) = await seed(
        user, "Deploy planning", date(2026, 10, 13), chunks=["Let's go with AWS ECS for hosting."],
        items=[{"topic": "deployment provider", "statement": "Host on AWS ECS.", "quote": "Let's go with AWS ECS for hosting.", "state": "superseded"},
               {"topic": "deployment provider", "statement": "ECS has credits.", "quote": "Let's go with AWS ECS for hosting.", "kind": "fact"}],
    )  # fmt: skip
    _, _, (render,) = await seed(
        user, "Deploy follow-up", date(2026, 10, 20), chunks=["Moving to Render."],
        items=[{"topic": "deployment provider", "statement": "Move to Render.", "quote": "Moving to Render.", "state": "decided"}],
    )  # fmt: skip
    _, _, (pg,) = await seed(
        user, "DB choice", date(2026, 10, 1), chunks=["Postgres it is."],
        items=[{"topic": "database choice", "statement": "Use Postgres.", "quote": "Postgres it is.", "state": "decided"}],
    )  # fmt: skip
    _, _, (my,) = await seed(
        user, "Analytics", date(2026, 10, 2), chunks=["MySQL it is."],
        items=[{"topic": "database choice", "statement": "Use MySQL.", "quote": "MySQL it is.", "state": "decided"}],
    )  # fmt: skip
    await seed(other, "Secret", date(2026, 10, 2), chunks=["secret"],
               items=[{"topic": "deployment provider", "statement": "Secret plan.", "quote": "secret", "state": "decided"}])  # fmt: skip
    async with get_sessionmaker()() as s:
        (await s.get(MemoryItem, ecs.id)).superseded_by_id = render.id
        (await s.get(MemoryItem, my.id)).conflict_with_id = pg.id
        (await s.get(MemoryItem, ecs.id)).chunk_id = chunks[0].id
        await s.commit()

    await login(user, pw)
    g = (await client.get("/api/v1/memories/graph")).json()
    nodes = {n["id"]: n for n in g["nodes"]}
    assert set(nodes) == {f"m:{i.id}" for i in (ecs, ecs_twin, render, pg, my)}  # never another user's
    assert nodes[f"m:{ecs.id}"]["chunk_ref"] == f"c:{chunks[0].id}"
    assert nodes[f"m:{ecs.id}"]["conversation_title"] == "Deploy planning"

    deploy = {nodes[f"m:{i.id}"]["cluster"] for i in (ecs, ecs_twin, render)}
    assert len(deploy) == 1 and None not in deploy
    labels = {c["id"]: c for c in g["clusters"]}
    assert labels[deploy.pop()]["label"] == "deployment provider"

    edges = {(e["a"], e["b"], e["type"]) for e in g["edges"]}
    assert (f"m:{ecs.id}", f"m:{render.id}", "supersedes") in edges
    assert (f"m:{my.id}", f"m:{pg.id}", "conflicts") in edges


async def test_graph_requires_auth(client):
    assert (await client.get("/api/v1/memories/graph")).status_code == 401
