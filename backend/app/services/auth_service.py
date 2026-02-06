"""Auth service: signup, login, refresh with session rotation, logout."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)
from app.models import RefreshSession
from app.repositories.user_repository import UserRepository
from app.schemas import UserCreate, UserResponse, Token, LoginRequest


def _expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def signup(self, data: UserCreate) -> UserResponse:
        existing = await self.user_repo.get_by_email(data.email)
        if existing:
            raise ValueError("Email already registered")
        user = await self.user_repo.create(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            name=data.name,
            bio=data.bio,
        )
        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def login(self, data: LoginRequest, user_agent: str | None = None, ip: str | None = None) -> Token:
        user = await self.user_repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise ValueError("Invalid email or password")
        access = create_access_token(str(user.id))
        refresh = create_refresh_token(str(user.id))
        session = RefreshSession(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(refresh),
            expires_at=_expires_at(),
            user_agent=user_agent,
            ip=ip,
        )
        self.db.add(session)
        await self.db.flush()
        return Token(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh_tokens(self, refresh_token: str) -> Token:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(RefreshSession).where(
                RefreshSession.refresh_token_hash == token_hash,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Invalid or expired refresh token")
        user = await self.user_repo.get_by_id(session.user_id)
        if not user:
            raise ValueError("User not found")
        # Rotate: new refresh token and update session
        new_refresh = create_refresh_token(str(user.id))
        session.refresh_token_hash = hash_refresh_token(new_refresh)
        session.last_used_at = now
        session.expires_at = _expires_at()
        await self.db.flush()
        access = create_access_token(str(user.id))
        return Token(
            access_token=access,
            refresh_token=new_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(RefreshSession).where(RefreshSession.refresh_token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if session:
            session.revoked_at = now
            await self.db.flush()
