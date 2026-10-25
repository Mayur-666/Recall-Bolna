"""Seed the demo account with clearly labeled sample conversations (repeatable).

  python scripts/seed_demo.py                    # demo account + samples, processed with the real model
  python scripts/seed_demo.py --second-user      # also the isolation account
  python scripts/seed_demo.py --refresh-dates    # move sample dates relative to today (before a demo)

Idempotent: the demo user is created only if missing (an existing account is never
modified), samples are added only if their content isn't already stored, and
conversations that aren't samples are never touched.
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.integrations.model_client import ModelClientProtocol, get_model_client  # noqa: E402
from app.models import Conversation, IngestionJob, User  # noqa: E402
from app.repositories.jobs import JobsRepo  # noqa: E402
from app.services.auth import AuthService  # noqa: E402
from app.services.dates import today_local  # noqa: E402
from app.services.ingestion import IngestionService, content_hash  # noqa: E402
from app.workers.ingestion_worker import process_job  # noqa: E402

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"


@dataclass
class SeedReport:
    created: int = 0
    skipped: int = 0
    redated: int = 0
    failed: int = 0


def load_manifest() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((SEED_DIR / "manifest.yaml").read_text(encoding="utf-8"))
    return data


async def _process(job_id: uuid.UUID, conv_id: uuid.UUID, model: ModelClientProtocol) -> str:
    sm = get_sessionmaker()
    async with sm() as s:
        claimed = await JobsRepo(s).claim(job_id)
        await s.commit()
    if claimed:
        await process_job(job_id, model)
    for _ in range(600):  # a running backend worker may own the job; wait for it
        async with sm() as s:
            conv = await s.get(Conversation, conv_id)
            if conv is not None and conv.status in ("ready", "failed"):
                return conv.status
        await asyncio.sleep(1)
    return "timeout"


async def seed_user(
    model: ModelClientProtocol,
    email: str,
    password: str,
    name: str,
    entries: list[dict[str, Any]],
    today: date,
    refresh_dates: bool,
    report: SeedReport,
) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        user: User = await AuthService(s).ensure_user(email, password, name)
        await s.commit()

    for entry in entries:
        text = (SEED_DIR / "conversations" / entry["file"]).read_text(encoding="utf-8")
        day = today - timedelta(days=int(entry["days_ago"]))
        async with sm() as s:
            existing = await s.scalar(
                select(Conversation).where(
                    Conversation.user_id == user.id, Conversation.content_hash == content_hash(text)
                )
            )
            if existing is not None:
                report.skipped += 1
                if refresh_dates and existing.is_sample and existing.conversation_date != day:
                    existing.conversation_date = day
                    report.redated += 1
                    await s.commit()
                continue
            conv = await IngestionService(s, model).create(
                user_id=user.id,
                title=entry["title"],
                conversation_date=day,
                participants=list(entry.get("participants") or []),
                self_speaker=entry.get("self_speaker"),
                text=text,
                source_type="paste",
                filename=entry["file"],
                is_sample=True,
            )
            await s.commit()
            job_id = await s.scalar(select(IngestionJob.id).where(IngestionJob.conversation_id == conv.id))
        assert job_id is not None
        status = await _process(job_id, conv.id, model)
        report.created += 1
        if status != "ready":
            report.failed += 1
            print(f"  ! {entry['title']}: {status}")
        else:
            print(f"  + {entry['title']} ({day})")


async def seed_all(
    model: ModelClientProtocol,
    email: str,
    password: str,
    name: str,
    include_second: bool,
    today: date,
    refresh_dates: bool = False,
    second_email: str | None = None,
) -> SeedReport:
    manifest = load_manifest()
    report = SeedReport()
    await seed_user(model, email, password, name, manifest["demo"], today, refresh_dates, report)
    if include_second:
        second = manifest["second_user"]
        await seed_user(
            model,
            second_email or second["email"],
            password + "-second",
            second["name"],
            second["conversations"],
            today,
            refresh_dates,
            report,
        )
    return report


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--second-user", action="store_true")
    ap.add_argument("--refresh-dates", action="store_true")
    args = ap.parse_args()
    s = get_settings()
    if not s.DEMO_PASSWORD:
        print("Set DEMO_PASSWORD in .env first.")
        return 2
    report = await seed_all(
        get_model_client(), s.DEMO_EMAIL, s.DEMO_PASSWORD, s.DEMO_NAME, args.second_user, today_local(),
        refresh_dates=args.refresh_dates,
    )  # fmt: skip
    print(
        f"created={report.created} skipped={report.skipped} redated={report.redated} failed={report.failed}"
    )
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
