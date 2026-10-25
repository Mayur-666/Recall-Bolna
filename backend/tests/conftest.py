import os

# Tests always run against the dedicated test database, never the dev one.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://recall:recall@localhost:5432/recall_test"
)
# Forced test values: never the developer's real secrets, and never a real Bolna account.
os.environ.update(
    {
        "WORKER_ENABLED": "false",
        "JWT_SECRET": "test-secret",
        "RECALL_TOOL_TOKEN": "test-tool-token",
        "BOLNA_API_KEY": "",
        "BOLNA_AGENT_ID": "",
        "PUBLIC_BASE_URL": "",
    }
)

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


@pytest.fixture
async def make_user(db_engine):
    """Create a user with a unique email; returns (user, password)."""
    import uuid

    from app.db.session import get_sessionmaker
    from app.services.auth import AuthService

    async def _make(name: str = "Tester", password: str = "pw-123456"):
        email = f"{uuid.uuid4().hex[:10]}@test.local"
        async with get_sessionmaker()() as session:
            user = await AuthService(session).ensure_user(email, password, name)
            await session.commit()
        return user, password

    return _make


@pytest.fixture
async def login(client):
    """Log the shared client in as the given user (cookie stored on the client)."""

    async def _login(user, password):
        resp = await client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
        assert resp.status_code == 200, resp.text
        return resp

    return _login
