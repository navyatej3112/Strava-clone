"""User profile service."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.schemas import UserResponse, UserUpdate, UserPublic


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def get_me(self, user_id: UUID) -> UserResponse | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        return UserResponse.model_validate(user)

    async def get_public(self, user_id: UUID) -> UserPublic | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        return UserPublic.model_validate(user)

    async def update_me(self, user_id: UUID, data: UserUpdate) -> UserResponse | None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        updates = data.model_dump(exclude_unset=True)
        await self.user_repo.update(user, **updates)
        await self.db.commit()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def search_users(self, query: str, limit: int = 20, offset: int = 0) -> list[UserPublic]:
        users = await self.user_repo.search_by_name(query, limit=limit, offset=offset)
        return [UserPublic.model_validate(u) for u in users]
