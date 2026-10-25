from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.users import UsersRepo

_INVALID = "Invalid email or password."


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UsersRepo(session)

    async def login(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError(_INVALID)
        return user

    async def ensure_user(self, email: str, password: str, display_name: str) -> User:
        """Idempotent: returns the existing user untouched, or creates it."""
        existing = await self.users.get_by_email(email)
        if existing is not None:
            return existing
        return await self.users.add(email, hash_password(password), display_name)
