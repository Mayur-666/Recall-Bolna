from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, current_user
from app.core.config import get_settings
from app.core.security import create_jwt
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    AuthConfigOut,
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from app.services.auth import AuthService
from app.services.call_sessions import CallSessionService

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_jwt(user_id),  # type: ignore[arg-type]
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_TTL_MIN * 60,
        path="/",
    )


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    user = await AuthService(db).login(body.email, body.password)
    _set_session_cookie(response, user.id)
    return user


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    user = await AuthService(db).register(body.display_name, body.email, body.password)
    _set_session_cookie(response, user.id)
    return user


@router.post("/google", response_model=UserOut)
async def google_auth(body: GoogleAuthRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    user = await AuthService(db).login_with_google(
        credential=body.credential,
        fallback_email=body.email,
        fallback_name=body.name,
    )
    _set_session_cookie(response, user.id)
    return user


@router.get("/config", response_model=AuthConfigOut)
async def auth_config() -> AuthConfigOut:
    settings = get_settings()
    return AuthConfigOut(google_client_id=settings.GOOGLE_CLIENT_ID)


@router.post("/logout", status_code=204)
async def logout(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Response:
    # Ending the web session also ends any voice call tokens it issued.
    await CallSessionService(db).revoke_all_for_user(user.id)
    await db.commit()
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> User:
    return user
