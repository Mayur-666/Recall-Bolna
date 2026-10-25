import uuid
from datetime import date

from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.models import Conversation, User
from app.services.ingestion import IngestionService
from scripts.seed_demo import seed_all
from tests.fakes import FakeModelClient

TODAY = date(2026, 10, 25)


async def _count(email, sample=None):
    async with get_sessionmaker()() as s:
        user = await s.scalar(select(User).where(User.email == email))
        stmt = select(func.count()).select_from(Conversation).where(Conversation.user_id == user.id)
        if sample is not None:
            stmt = stmt.where(Conversation.is_sample == sample)
        return user, await s.scalar(stmt)


async def test_seed_idempotent_and_preserves_user_data():
    email = f"demo-{uuid.uuid4().hex[:8]}@test.local"
    model = FakeModelClient()
    report = await seed_all(model, email, "pw-123456", "Mayur", include_second=False, today=TODAY)
    assert report.created == 9 and report.skipped == 0
    user, n_sample = await _count(email, sample=True)
    assert n_sample == 9

    # The user adds their own conversation between seed runs.
    async with get_sessionmaker()() as s:
        own = await IngestionService(s).create(
            user_id=user.id, title="My own call", conversation_date=TODAY, participants=[], self_speaker=None,
            text="Mayur: this is mine, not a sample.", source_type="paste", filename=None,
        )  # fmt: skip
        await s.commit()

    again = await seed_all(
        model, email, "different-password", "Someone Else", include_second=False, today=TODAY
    )
    assert again.created == 0 and again.skipped == 9
    _, total = await _count(email)
    assert total == 10
    async with get_sessionmaker()() as s:
        kept = await s.get(Conversation, own.id)
        refreshed_user = await s.get(User, user.id)
    assert kept is not None and kept.title == "My own call" and kept.is_sample is False
    assert refreshed_user.display_name == "Mayur"  # existing account untouched


async def test_seed_processes_to_ready_and_dates_are_relative():
    email = f"demo-{uuid.uuid4().hex[:8]}@test.local"
    await seed_all(FakeModelClient(), email, "pw-123456", "Mayur", include_second=False, today=TODAY)
    async with get_sessionmaker()() as s:
        user = await s.scalar(select(User).where(User.email == email))
        rows = (await s.scalars(select(Conversation).where(Conversation.user_id == user.id))).all()
    assert {r.status for r in rows} == {"ready"}
    by_title = {r.title: r for r in rows}
    assert by_title["API design sync"].conversation_date == date(2026, 10, 16)
    assert by_title["API design sync"].self_speaker == "Mayur"


async def test_refresh_dates_moves_sample_dates_only():
    email = f"demo-{uuid.uuid4().hex[:8]}@test.local"
    await seed_all(FakeModelClient(), email, "pw", "Mayur", include_second=False, today=TODAY)
    later = date(2026, 10, 31)
    report = await seed_all(
        FakeModelClient(), email, "pw", "Mayur", include_second=False, today=later, refresh_dates=True
    )
    assert report.redated == 9
    async with get_sessionmaker()() as s:
        user = await s.scalar(select(User).where(User.email == email))
        conv = await s.scalar(
            select(Conversation).where(
                Conversation.user_id == user.id, Conversation.title == "API design sync"
            )
        )
    assert conv.conversation_date == date(2026, 10, 22)


async def test_second_user_seeded_separately():
    email = f"demo-{uuid.uuid4().hex[:8]}@test.local"
    second = f"second-{uuid.uuid4().hex[:8]}@test.local"
    await seed_all(
        FakeModelClient(), email, "pw", "Mayur", include_second=True, today=TODAY, second_email=second
    )
    other, n = await _count(second)
    assert n == 1 and other.display_name == "Omar"
