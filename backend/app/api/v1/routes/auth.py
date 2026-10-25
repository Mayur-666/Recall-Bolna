from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, current_user
from app.core.config import get_settings
from app.core.security import create_jwt
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, UserOut
from app.services.auth import AuthService
from app.services.call_sessions import CallSessionService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    user = await AuthService(db).login(body.email, body.password)
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_jwt(user.id),
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_TTL_MIN * 60,
        path="/",
    )
    return user


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
