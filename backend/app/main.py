from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.db.dim_guard import check_embedding_dim
from app.db.session import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with get_engine().connect() as conn:
        await check_embedding_dim(conn, get_settings().EMBED_DIM)
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Recall API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
