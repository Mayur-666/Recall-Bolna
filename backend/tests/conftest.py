import os

# Tests always run against the dedicated test database, never the dev one.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://recall:recall@localhost:5432/recall_test"
)
os.environ.setdefault("WORKER_ENABLED", "false")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("RECALL_TOOL_TOKEN", "test-tool-token")

import asyncio  # noqa: E402
import subprocess  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Fresh schema per test session: drop everything, then run the real migrations."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await asyncio.to_thread(subprocess.run, ["alembic", "upgrade", "head"], check=True, env=os.environ.copy())
    yield engine


@pytest.fixture
async def client(db_engine) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
