import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.bolna.tunnel_sync import run_tunnel_sync, sync_enabled
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.db.dim_guard import check_embedding_dim
from app.db.session import get_engine
from app.integrations.model_client import get_model_client
from app.workers.ingestion_worker import run_worker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with get_engine().connect() as conn:
        await check_embedding_dim(conn, get_settings().EMBED_DIM)
    # Load the embedding model in the background so the first question isn't a cold start.
    warm = asyncio.create_task(get_model_client().warm_up())
    stop = asyncio.Event()
    worker = asyncio.create_task(run_worker(stop)) if get_settings().WORKER_ENABLED else None
    # Point the Bolna agent at the current tunnel URL, and again whenever the tunnel restarts.
    tunnel = asyncio.create_task(run_tunnel_sync(stop)) if sync_enabled() else None
    yield
    stop.set()
    warm.cancel()
    if worker is not None:
        await worker
    if tunnel is not None:
        await tunnel


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Recall API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
