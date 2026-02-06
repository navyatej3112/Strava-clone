"""User repository."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, hashed_password: str, name: str, bio: str | None = None) -> User:
        user = User(email=email, hashed_password=hashed_password, name=name, bio=bio)
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update(self, user: User, **kwargs: object) -> User:
        for k, v in kwargs.items():
            if hasattr(user, k):
                setattr(user, k, v)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def search_by_name(self, query: str, limit: int = 20, offset: int = 0) -> list[User]:
        q = select(User).where(User.name.ilike(f"%{query}%")).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().all())
