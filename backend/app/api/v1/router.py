from fastapi import APIRouter

from app.api.v1.routes import auth, bolna_tools, calls, conversations, health, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(search.router)
api_router.include_router(bolna_tools.router)
api_router.include_router(calls.router)
