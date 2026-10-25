from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.core.security import decode_jwt
from app.db.session import get_db
from app.models import User
from app.repositories.users import UsersRepo

SESSION_COOKIE = "recall_session_jwt"


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AuthError()
    user = await UsersRepo(db).get(decode_jwt(token))
    if user is None:
        raise AuthError()
    return user
