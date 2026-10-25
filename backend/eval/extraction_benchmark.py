"""Benchmark extraction models on the seed transcripts against hand-written gold items.

  python eval/extraction_benchmark.py --models qwen2.5:7b-instruct,llama3.1:8b

For each model: ingest every demo seed transcript for a throwaway user through the real
pipeline (parse -> chunk -> embed -> extract -> link), score against eval/gold_extractions.yaml,
record timings and GPU memory, then delete the throwaway user. Writes docs/model-benchmark.md.
Stop the backend first (`docker compose stop backend`) so its worker can't pick up these jobs.
"""

import argparse
import asyncio
import statistics
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.integrations.model_client import ModelClient  # noqa: E402
from app.models import Conversation, IngestionJob, MemoryItem, User  # noqa: E402
from scripts.seed_demo import SeedReport, load_manifest, seed_user  # noqa: E402

BAR = {"quote_validity": 0.95, "decision_state_accuracy": 0.85, "max_seconds_per_transcript": 60.0}
KIND_GROUPS = {"commitment": {"commitment", "action_item"}}


def _kinds(gold_kind: Any) -> set[str]:
    kinds = set(gold_kind) if isinstance(gold_kind, list) else {gold_kind}
    out: set[str] = set()
    for k in kinds:
        out |= KIND_GROUPS.get(k, {k})
    return out


def _matches(gold: dict[str, Any], item: MemoryItem) -> bool:
    text = f"{item.statement} {item.evidence_quote}".lower()
    return item.kind in _kinds(gold["kind"]) and all(p.lower() in text for p in gold["match"])


async def ollama_ps() -> list[dict[str, Any]]:
    base = get_settings().MODEL_BASE_URL.removesuffix("/v1")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{base}/api/ps")
        models: list[dict[str, Any]] = r.json().get("models", [])
        return models
    except (httpx.HTTPError, ValueError):
        return []


async def run_model(model_name: str, today: date) -> dict[str, Any]:
    settings = get_settings()
    settings.EXTRACT_MODEL = model_name
    client = ModelClient()
    t = time.perf_counter()
    await client.chat_json(
        "Reply with JSON.", "Say ok.", {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    )
    cold_s = time.perf_counter() - t

    email = f"bench-{uuid.uuid4().hex[:8]}@bench.local"
    manifest = load_manifest()
    report = SeedReport()
    t = time.perf_counter()
    await seed_user(client, email, "bench", "Mayur", manifest["demo"], today, False, report)
    wall_s = time.perf_counter() - t
    ps = await ollama_ps()

    gold_all: dict[str, list[dict[str, Any]]] = yaml.safe_load(
        (ROOT / "eval" / "gold_extractions.yaml").read_text()
    )
    sm = get_sessionmaker()
    async with sm() as s:
        user = await s.scalar(select(User).where(User.email == email))
        assert user is not None
        convs = {
            c.original_filename: c
            for c in (await s.scalars(select(Conversation).where(Conversation.user_id == user.id))).all()
        }
        items = (await s.scalars(select(MemoryItem).where(MemoryItem.user_id == user.id))).all()
        jobs = (await s.scalars(select(IngestionJob).where(IngestionJob.user_id == user.id))).all()

    kept = sum((j.timings or {}).get("extraction", {}).get("kept", 0) for j in jobs)
    unlocated = sum((j.timings or {}).get("extraction", {}).get("rejected_unlocated", 0) for j in jobs)
    bad_speaker = sum((j.timings or {}).get("extraction", {}).get("rejected_bad_speaker", 0) for j in jobs)
    secs = [(j.timings or {}).get("total_ms", 0) / 1000 for j in jobs]

    found = state_ok = state_total = speaker_ok = speaker_total = owner_ok = owner_total = 0
    false_decided = change_ok = change_total = 0
    misses: list[str] = []
    for fname, golds in gold_all.items():
        conv = convs.get(fname)
        conv_items = [i for i in items if conv and i.conversation_id == conv.id]
        for g in golds:
            hit = next((i for i in conv_items if _matches(g, i)), None)
            if hit is None:
                misses.append(f"{fname}: {g['kind']} {g['match']}")
            else:
                found += 1
            if "states" in g:
                state_total += 1
                if hit is not None and hit.decision_state in g["states"] + (
                    ["superseded"] if "superseded_by_file" in g else []
                ):
                    state_ok += 1
            if g.get("never_decided") and hit is not None and hit.decision_state == "decided":
                false_decided += 1
            if "speaker" in g and hit is not None:
                speaker_total += 1
                speaker_ok += int(hit.speaker == g["speaker"])
            if "owner" in g:
                owner_total += 1
                if (
                    hit is not None
                    and hit.owner == g["owner"]
                    and hit.owner_is_user == g.get("owner_is_user", False)
                ):
                    owner_ok += 1
            if "superseded_by_file" in g:
                change_total += 1
                target = convs.get(g["superseded_by_file"])
                later = [
                    i for i in items if target and i.conversation_id == target.id and i.kind == "decision"
                ]
                if (
                    hit is not None
                    and hit.decision_state == "superseded"
                    and hit.superseded_by_id in {i.id for i in later}
                ):
                    change_ok += 1

    total_gold = sum(len(v) for v in gold_all.values())
    result = {
        "model": model_name,
        "cold_load_s": round(cold_s, 1),
        "wall_s": round(wall_s, 1),
        "sec_per_transcript_avg": round(statistics.mean(secs), 1) if secs else None,
        "sec_per_transcript_max": round(max(secs), 1) if secs else None,
        "items_kept": kept,
        "quote_validity": round(kept / (kept + unlocated), 3) if kept + unlocated else 0.0,
        "speaker_overrides": bad_speaker,
        "gold_recall": round(found / total_gold, 3),
        "decision_state_accuracy": round(state_ok / state_total, 3) if state_total else None,
        "speaker_accuracy": round(speaker_ok / speaker_total, 3) if speaker_total else None,
        "commitment_owner_accuracy": round(owner_ok / owner_total, 3) if owner_total else None,
        "false_decided_on_open_discussion": false_decided,
        "change_detection": f"{change_ok}/{change_total}",
        "failed_conversations": report.failed,
        "vram_mb": {m.get("name"): round(m.get("size_vram", 0) / 2**20) for m in ps},
        "misses": misses,
    }
    result["passes_bar"] = (
        result["quote_validity"] >= BAR["quote_validity"]
        and (result["decision_state_accuracy"] or 0) >= BAR["decision_state_accuracy"]
        and change_ok == change_total
        and false_decided == 0
        and (result["sec_per_transcript_max"] or 0) <= BAR["max_seconds_per_transcript"]
        and report.failed == 0
    )
    async with sm() as s:
        await s.execute(delete(User).where(User.id == user.id))
        await s.commit()
    return result


def write_report(results: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Extraction model benchmark",
        "",
        f"Run: {time.strftime('%Y-%m-%d %H:%M')} · embedding model: {get_settings().EMBED_MODEL} · "
        f"bar: quote validity ≥ {BAR['quote_validity']:.0%}, decision-state accuracy ≥ {BAR['decision_state_accuracy']:.0%}, "
        f"ECS→Render change detected, open pricing never 'decided', ≤ {BAR['max_seconds_per_transcript']:.0f} s per transcript.",
        "",
        "| Metric | " + " | ".join(r["model"] for r in results) + " |",
        "|---|" + "---|" * len(results),
    ]
    keys = [k for k in results[0] if k not in ("model", "misses")]
    for k in keys:
        lines.append(f"| {k} | " + " | ".join(str(r[k]) for r in results) + " |")
    lines.append("")
    for r in results:
        lines.append(f"**{r['model']} — gold items not found:** " + ("; ".join(r["misses"]) or "none"))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", default=str(ROOT.parent / "docs" / "model-benchmark.md"))
    args = ap.parse_args()
    today = date.today()
    results = []
    for name in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"== {name}")
        r = await run_model(name, today)
        print({k: v for k, v in r.items() if k != "misses"})
        results.append(r)
    write_report(results, Path(args.out))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
