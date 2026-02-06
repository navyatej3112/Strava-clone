"""Follow/unfollow and list followers/following."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.follow_repository import FollowRepository
from app.repositories.user_repository import UserRepository
from app.schemas import UserPublic


class FollowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.follow_repo = FollowRepository(db)
        self.user_repo = UserRepository(db)

    async def follow(self, follower_id: UUID, followed_id: UUID) -> bool:
        if follower_id == followed_id:
            return False
        followed = await self.user_repo.get_by_id(followed_id)
        if not followed:
            return False
        already = await self.follow_repo.is_following(follower_id, followed_id)
        if already:
            return True
        await self.follow_repo.follow(follower_id, followed_id)
        await self.db.commit()
        return True

    async def unfollow(self, follower_id: UUID, followed_id: UUID) -> bool:
        ok = await self.follow_repo.unfollow(follower_id, followed_id)
        if ok:
            await self.db.commit()
        return ok

    async def is_following(self, follower_id: UUID, followed_id: UUID) -> bool:
        return await self.follow_repo.is_following(follower_id, followed_id)

    async def get_following(self, user_id: UUID, limit: int = 50, offset: int = 0) -> list[UserPublic]:
        followed_ids = await self.follow_repo.get_followed_ids(user_id)
        followed_ids = followed_ids[offset : offset + limit]
        out = []
        for fid in followed_ids:
            u = await self.user_repo.get_by_id(fid)
            if u:
                out.append(UserPublic.model_validate(u))
        return out

    async def get_followers(self, user_id: UUID, limit: int = 50, offset: int = 0) -> list[UserPublic]:
        follower_ids = await self.follow_repo.get_follower_ids(user_id)
        follower_ids = follower_ids[offset : offset + limit]
        out = []
        for fid in follower_ids:
            u = await self.user_repo.get_by_id(fid)
            if u:
                out.append(UserPublic.model_validate(u))
        return out
