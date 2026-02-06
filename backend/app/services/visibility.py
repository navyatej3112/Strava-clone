"""Visibility rules: who can view an activity."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityVisibility
from app.repositories.follow_repository import FollowRepository


async def can_view_activity(
    db: AsyncSession,
    requester_id: UUID | None,
    activity_owner_id: UUID,
    visibility: ActivityVisibility,
) -> bool:
    """
    Owner can always view. Others:
    - public: always
    - followers: only if requester follows owner
    - private: never
    """
    if requester_id == activity_owner_id:
        return True
    if visibility == ActivityVisibility.PUBLIC:
        return True
    if visibility == ActivityVisibility.PRIVATE:
        return False
    if visibility == ActivityVisibility.FOLLOWERS:
        if requester_id is None:
            return False
        follow_repo = FollowRepository(db)
        return await follow_repo.is_following(requester_id, activity_owner_id)
    return False
