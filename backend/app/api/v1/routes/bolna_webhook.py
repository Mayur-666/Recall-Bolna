"""Bolna execution webhook. Payload shape = GET /executions/{id} (Bolna skills: execution-payload.md).

Accepted only from Bolna's documented webhook IP, and only for executions linked to a
known call session. Multiple deliveries per execution are expected; each is treated as
the latest known state, and a stored transcript is never overwritten.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.db.session import get_db
from app.repositories.call_sessions import CallSessionsRepo
from app.services.calls import CallsService

log = logging.getLogger(__name__)
router = APIRouter(prefix="/bolna", tags=["bolna-webhook"])


def client_ip(request: Request) -> str:
    # Through the Cloudflare tunnel, CF-Connecting-IP is set by Cloudflare itself.
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/webhook")
async def bolna_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    if client_ip(request) != get_settings().BOLNA_WEBHOOK_IP:
        log.warning("webhook rejected: unexpected source")
        raise ForbiddenError("Webhook source not allowed.")
    payload: dict[str, Any] = await request.json()
    execution_id = str(payload.get("id") or "")
    cs = await CallSessionsRepo(db).get_by_execution(execution_id) if execution_id else None
    if cs is None:
        return JSONResponse({"status": "ignored"}, status_code=202)
    await CallsService(db).apply_execution(cs, payload)
    return JSONResponse({"status": "ok"})
