from fastapi import APIRouter

from app.api.v1.routes import auth, bolna_tools, bolna_webhook, calls, conversations, health, memories, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(search.router)
api_router.include_router(memories.router)
api_router.include_router(bolna_tools.router)
api_router.include_router(calls.router)
api_router.include_router(bolna_webhook.router)
