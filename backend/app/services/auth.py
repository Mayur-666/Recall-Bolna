import logging
import secrets
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.email_validator import ensure_valid_email
from app.core.errors import AuthError, ConflictError, ValidationAppError
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.users import UsersRepo

log = logging.getLogger(__name__)
_INVALID = "Invalid email or password."
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UsersRepo(session)
        self.settings = get_settings()

    async def login(self, email: str, password: str) -> User:
        norm_email = ensure_valid_email(email)
        user = await self.users.get_by_email(norm_email)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError(_INVALID)
        return user

    async def register(self, display_name: str, email: str, password: str) -> User:
        norm_email = ensure_valid_email(email)
        clean_name = display_name.strip()
        if len(clean_name) < 2:
            raise ValidationAppError("Display name must be at least 2 characters long.")
        if len(password) < 6:
            raise ValidationAppError("Password must be at least 6 characters long.")

        existing = await self.users.get_by_email(norm_email)
        if existing is not None:
            raise ConflictError("An account with this email address already exists. Please sign in instead.")

        hashed = hash_password(password)
        user = await self.users.add(norm_email, hashed, clean_name)
        await self.session.commit()
        return user

    async def login_with_google(
        self, credential: str, fallback_email: str | None = None, fallback_name: str | None = None
    ) -> User:
        """Verify Google ID token via Google tokeninfo or handle dev simulation.

        Idempotently returns existing user or registers a new account for the verified Google email.
        """
        verified_email: str | None = None
        verified_name: str | None = None

        # 1. Attempt official Google ID token verification if credential looks like a JWT
        if credential and credential.count(".") == 2 and not credential.startswith("demo_google"):
            try:
                async with httpx.AsyncClient(timeout=10.0) as http:
                    resp = await http.get(_GOOGLE_TOKENINFO_URL, params={"id_token": credential})
                    if resp.status_code == 200:
                        payload: dict[str, Any] = resp.json()
                        email_str = payload.get("email")
                        if email_str and str(payload.get("email_verified", "")).lower() in ("true", "1"):
                            # If client ID is configured, verify audience matches
                            aud = payload.get("aud")
                            if self.settings.GOOGLE_CLIENT_ID and aud != self.settings.GOOGLE_CLIENT_ID:
                                log.warning("Google ID token audience mismatch: %s != %s", aud, self.settings.GOOGLE_CLIENT_ID)
                                raise AuthError("Google authentication token audience mismatch.")

                            verified_email = email_str
                            verified_name = payload.get("name") or payload.get("given_name")
            except httpx.HTTPError as exc:
                log.warning("Could not reach Google tokeninfo endpoint: %s", exc)

        # 2. Dev simulation (caller-supplied email, unverified) ONLY when no Google client is configured.
        # Once GOOGLE_CLIENT_ID is set, a verified Google ID token is the only way in — otherwise anyone
        # could sign in as any email by sending a "demo_google:..." credential.
        if not verified_email:
            if fallback_email and not self.settings.GOOGLE_CLIENT_ID:
                verified_email = fallback_email
                verified_name = fallback_name
            else:
                raise AuthError("Google authentication failed. Please try again or sign in with email and password.")

        norm_email = ensure_valid_email(verified_email)
        display_name = (verified_name or norm_email.split("@")[0]).strip()[:100]

        # 3. Get or create user
        existing = await self.users.get_by_email(norm_email)
        if existing is not None:
            return existing

        # New user via Google: generate secure random password
        random_pwd = secrets.token_urlsafe(32)
        user = await self.users.add(norm_email, hash_password(random_pwd), display_name)
        await self.session.commit()
        return user

    async def ensure_user(self, email: str, password: str, display_name: str) -> User:
        """Idempotent: returns the existing user untouched, or creates it."""
        existing = await self.users.get_by_email(email)
        if existing is not None:
            return existing
        return await self.users.add(email, hash_password(password), display_name)
