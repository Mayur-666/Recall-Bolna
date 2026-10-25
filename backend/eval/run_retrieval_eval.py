"""Retrieval evaluation on the seeded demo account with the real embedding model.

  python scripts/seed_demo.py --second-user      # once
  python eval/run_retrieval_eval.py               # writes docs/eval-results.md, exits 1 on any failure

Measures retrieval behaviour (what search_memories returns) separately from answer quality
(what the voice agent says), which is checked in the live Bolna session.
"""

import argparse
import asyncio
import statistics
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.integrations.model_client import get_model_client  # noqa: E402
from app.models import Conversation, User  # noqa: E402
from app.schemas.search import SearchQuery, SearchResult  # noqa: E402
from app.services.dates import parse_relative_range, today_local  # noqa: E402
from app.services.retrieval import RetrievalService  # noqa: E402

LATENCY_BUDGET_P95_MS = 500.0
PENDING_TITLE = "Mobile release planning (pending)"


def check(case: dict[str, Any], r: SearchResult, today: date) -> list[str]:
    exp = case["expect"]
    errs: list[str] = []
    titles = [e.conversation_title for e in r.results]
    text = lambda e: f"{e.statement or ''} {e.excerpt}".lower()  # noqa: E731
    if r.status not in exp["status_in"]:
        errs.append(f"status {r.status} not in {exp['status_in']}")
    if "top3_title" in exp and exp["top3_title"] not in titles[:3]:
        errs.append(f"'{exp['top3_title']}' not in top 3 {titles[:3]}")
    if "top3_title_in" in exp and not set(exp["top3_title_in"]) & set(titles[:3]):
        errs.append(f"none of {exp['top3_title_in']} in top 3 {titles[:3]}")
    if "top3_speaker" in exp and not any(exp["top3_speaker"] in (e.speaker or "") for e in r.results[:3]):
        errs.append(f"speaker {exp['top3_speaker']} not in top 3")
    if "top3_mentions_speaker" in exp:
        who = exp["top3_mentions_speaker"]
        if not any(who in (e.speaker or "") or f"{who}:" in e.excerpt for e in r.results[:3]):
            errs.append(f"{who} not attributed in top 3")
    if "top1_speaker_in" in exp and (not r.results or r.results[0].speaker not in exp["top1_speaker_in"]):
        errs.append(
            f"top speaker {r.results[0].speaker if r.results else None} not in {exp['top1_speaker_in']}"
        )
    if exp.get("all_dates_in") == "last_week":
        d0, d1 = parse_relative_range("last week", today) or (today, today)
        # Decisions pulled in because they supersede/conflict with a result may lie outside the window.
        bad = [
            str(e.conversation_date)
            for e in r.results
            if e.related_to_ref is None and not d0 <= e.conversation_date <= d1
        ]
        if bad:
            errs.append(f"results outside last week {d0}..{d1}: {bad}")
    if "has_item" in exp:
        m = exp["has_item"]
        if not any(m["match"] in text(e) and e.decision_state == m["state"] for e in r.results):
            errs.append(f"no {m['state']} item matching '{m['match']}'")
    if "if_present" in exp:
        m = exp["if_present"]
        for e in r.results:
            if e.kind == "decision" and m["match"] in text(e) and e.decision_state != m["state"]:
                errs.append(
                    f"'{m['match']}' decision present with state {e.decision_state}, expected {m['state']}"
                )
    if exp.get("postgres_mysql_not_silently_merged"):
        decided = [e for e in r.results if e.kind == "decision" and e.decision_state == "decided"]
        pg = [e for e in decided if "postgres" in text(e)]
        my = [e for e in decided if "mysql" in text(e)]
        if (
            pg
            and my
            and not (all(e.conflict for e in pg + my) or "analytics" in " ".join(text(e) for e in my))
        ):
            errs.append("Postgres and MySQL both 'decided' without conflict flag or distinct scope")
    if "no_titles" in exp and set(exp["no_titles"]) & set(titles):
        errs.append(f"leaked titles {set(exp['no_titles']) & set(titles)}")
    if "pending_contains" in exp and exp["pending_contains"] not in r.pending_conversations:
        errs.append(f"pending list {r.pending_conversations} lacks '{exp['pending_contains']}'")
    if "has_owner_is_user" in exp and not any(
        e.owner_is_user and exp["has_owner_is_user"] in text(e) for e in r.results
    ):
        errs.append(f"no owner_is_user item matching '{exp['has_owner_is_user']}'")
    if "no_decided_match" in exp and any(
        e.decision_state == "decided" and exp["no_decided_match"] in text(e) for e in r.results
    ):
        errs.append(f"a '{exp['no_decided_match']}' item is marked decided")
    if exp.get("degraded") and not r.degraded:
        errs.append("expected degraded keyword-only mode")
    return errs


async def run(out: Path) -> int:
    settings = get_settings()
    sm = get_sessionmaker()
    model = get_model_client()
    await model.warm_up()
    today = today_local()
    async with sm() as s:
        user = await s.scalar(select(User).where(User.email == settings.DEMO_EMAIL))
    if user is None:
        print("Demo user missing: run scripts/seed_demo.py --second-user first.")
        return 2

    cases = yaml.safe_load((ROOT / "eval" / "cases.yaml").read_text())["cases"]
    refs: dict[str, str] = {}
    rows: list[tuple[str, bool, str, str]] = []
    diagnostics: list[str] = []
    for case in cases:
        setup = case.get("setup")
        pending_id = None
        if setup == "queued_conversation":
            async with sm() as s:
                conv = Conversation(
                    user_id=user.id, title=PENDING_TITLE, conversation_date=today, participants=[],
                    source_type="paste", transcript_text="pending", content_hash=f"eval-pending-{time.time()}",
                    status="queued",
                )  # fmt: skip
                s.add(conv)
                await s.commit()
                pending_id = conv.id
        saved_timeout = settings.EMBED_TIMEOUT_S
        if setup == "embedding_timeout":
            settings.EMBED_TIMEOUT_S = 0.0005
        try:
            prev = refs.get(case.get("previous_ref_from", ""))
            async with sm() as s:
                r = await RetrievalService(s, model).search(
                    user.id,
                    SearchQuery(
                        question=case["question"],
                        standalone_query=case.get("standalone_query"),
                        previous_result_ref=prev,
                    ),
                    today,
                )
        finally:
            settings.EMBED_TIMEOUT_S = saved_timeout
            if pending_id is not None:
                async with sm() as s:
                    await s.execute(delete(Conversation).where(Conversation.id == pending_id))
                    await s.commit()
        if r.results:
            refs[case["id"]] = r.results[0].ref
        errs = check(case, r, today)
        rows.append((case["id"], not errs, r.status, "; ".join(errs)))
        diag = ", ".join(
            f"{e.conversation_title}/{e.kind}/{e.decision_state or '-'}/fused {e.score:.4f}/sim {e.vector_similarity}"
            f"{'/weak' if e.weak else ''}{'/related' if e.related_to_ref else ''}"
            for e in r.results
        )
        diagnostics.append(
            f"- `{case['id']}` ({r.status}, {r.timings_ms.get('total')} ms): {diag or 'no results'}"
        )
        print(f"[{'PASS' if not errs else 'FAIL'}] {case['id']:28} {r.status:20} {'; '.join(errs)}")

    # Warm latency: a realistic mix of questions, 100 searches.
    questions = [c["question"] for c in cases if not c.get("setup")]
    totals: list[float] = []
    stages: dict[str, list[float]] = {}
    async with sm() as s:
        svc = RetrievalService(s, model)
        for i in range(100):
            r = await svc.search(user.id, SearchQuery(question=questions[i % len(questions)]), today)
            totals.append(r.timings_ms["total"])
            for k, v in r.timings_ms.items():
                stages.setdefault(k, []).append(v)
            await s.rollback()
    q = statistics.quantiles(totals, n=100)
    p50, p95 = statistics.median(totals), q[94]
    latency_ok = p95 < LATENCY_BUDGET_P95_MS
    stage_line = ", ".join(
        f"{k} p50 {statistics.median(v):.1f} ms / p95 {statistics.quantiles(v, n=100)[94]:.1f} ms"
        for k, v in stages.items()
    )
    print(
        f"latency: p50 {p50:.1f} ms, p95 {p95:.1f} ms (budget {LATENCY_BUDGET_P95_MS} ms) -> {'PASS' if latency_ok else 'FAIL'}"
    )

    passed = sum(1 for r in rows if r[1])
    lines = [
        "# Retrieval evaluation results",
        "",
        f"Run: {time.strftime('%Y-%m-%d %H:%M')} · today={today} · embed={settings.EMBED_MODEL} · "
        f"RETRIEVAL_MIN_VECTOR_SIM={settings.RETRIEVAL_MIN_VECTOR_SIM} · AMBIGUITY_MARGIN={settings.AMBIGUITY_MARGIN} · "
        f"LINK_MIN_SIM={settings.LINK_MIN_SIM}",
        "",
        f"**Cases: {passed}/{len(rows)} passed.** Latency over 100 warm searches: p50 {p50:.1f} ms, "
        f"p95 {p95:.1f} ms (budget p95 < {LATENCY_BUDGET_P95_MS:.0f} ms: {'PASS' if latency_ok else 'FAIL'}).",
        "",
        "| Case | Result | Status | Notes |",
        "|---|---|---|---|",
        *[f"| {cid} | {'PASS' if ok else 'FAIL'} | {st} | {note} |" for cid, ok, st, note in rows],
        "",
        f"Stage latency: {stage_line}",
        "",
        "Returned evidence per case (title/kind/state/fused score/vector similarity):",
        "",
        *diagnostics,
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    return 0 if passed == len(rows) and latency_ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "docs" / "eval-results.md"))
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(Path(args.out))))
