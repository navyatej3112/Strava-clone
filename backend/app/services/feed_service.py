"""Feed: activities from self + followed users with filters."""
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivitySportType
from app.repositories.activity_repository import ActivityRepository
from app.repositories.follow_repository import FollowRepository
from app.schemas import ActivityListResponse, UserPublic, SportType, Visibility, ActivityStatus


class FeedService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_repo = ActivityRepository(db)
        self.follow_repo = FollowRepository(db)

    async def get_feed(
        self,
        user_id: UUID,
        sport_type: SportType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ActivityListResponse]:
        followed_ids = await self.follow_repo.get_followed_ids(user_id)
        sport_enum = ActivitySportType(sport_type.value) if sport_type else None
        activities = await self.activity_repo.get_feed(
            user_id=user_id,
            follower_ids=followed_ids,
            sport_type=sport_enum,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        out = []
        for a in activities:
            like_count = await self.activity_repo.count_likes(a.id)
            from sqlalchemy import select, func
            from app.models import Comment
            r = await self.db.execute(select(func.count(Comment.id)).where(Comment.activity_id == a.id))
            comment_count = r.scalar() or 0
            from app.models import Like
            r2 = await self.db.execute(select(Like).where(Like.activity_id == a.id, Like.user_id == user_id))
            liked_by_me = r2.scalar_one_or_none() is not None
            user_public = UserPublic.model_validate(a.user) if a.user else None
            out.append(
                ActivityListResponse(
                    id=a.id,
                    user_id=a.user_id,
                    title=a.title,
                    sport_type=SportType(a.sport_type.value),
                    visibility=Visibility(a.visibility.value),
                    started_at=a.started_at,
                    distance_m=a.distance_m,
                    duration_s=a.duration_s,
                    elevation_gain_m=a.elevation_gain_m,
                    calories=a.calories,
                    polyline=a.polyline,
                    created_at=a.created_at,
                    like_count=like_count,
                    comment_count=comment_count,
                    liked_by_me=liked_by_me,
                    user=user_public,
                    status=ActivityStatus(a.status.value),
                )
            )
        return out
