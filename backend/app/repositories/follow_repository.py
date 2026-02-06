"""Follow repository."""
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Follow, User


class FollowRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def follow(self, follower_id: UUID, followed_id: UUID) -> Follow:
        follow = Follow(follower_id=follower_id, followed_id=followed_id)
        self.db.add(follow)
        await self.db.flush()
        await self.db.refresh(follow)
        return follow

    async def unfollow(self, follower_id: UUID, followed_id: UUID) -> bool:
        result = await self.db.execute(delete(Follow).where(Follow.follower_id == follower_id, Follow.followed_id == followed_id))
        return result.rowcount > 0

    async def is_following(self, follower_id: UUID, followed_id: UUID) -> bool:
        result = await self.db.execute(
            select(Follow).where(Follow.follower_id == follower_id, Follow.followed_id == followed_id)
        )
        return result.scalar_one_or_none() is not None

    async def get_followed_ids(self, follower_id: UUID) -> list[UUID]:
        result = await self.db.execute(select(Follow.followed_id).where(Follow.follower_id == follower_id))
        return list(result.scalars().all())

    async def get_follower_ids(self, followed_id: UUID) -> list[UUID]:
        result = await self.db.execute(select(Follow.follower_id).where(Follow.followed_id == followed_id))
        return list(result.scalars().all())
