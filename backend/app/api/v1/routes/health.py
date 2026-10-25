import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "down"

    # The model endpoint being down degrades search; it doesn't make the API unhealthy.
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=1.0) as c:
            r = await c.get(f"{settings.MODEL_BASE_URL}/models")
        model_status = "ok" if r.status_code == 200 else "down"
    except httpx.HTTPError:
        model_status = "down"

    return {"status": "ok" if db_status == "ok" else "degraded", "db": db_status, "model": model_status}
