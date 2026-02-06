"""Activity repository."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Activity, User, Like
from app.models.activity import ActivitySportType, ActivityVisibility, ActivityStatus


class ActivityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, activity_id: UUID, load_user: bool = False) -> Activity | None:
        q = select(Activity).where(Activity.id == activity_id)
        if load_user:
            q = q.options(selectinload(Activity.user))
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        title: str,
        sport_type: ActivitySportType,
        visibility: ActivityVisibility,
        started_at: datetime,
        *,
        distance_m=None,
        duration_s=None,
        elevation_gain_m=None,
        calories=None,
        polyline=None,
        raw_file_path=None,
        status: ActivityStatus = ActivityStatus.READY,
        rank_eligible=True,
        rank_excluded_reason=None,
        max_speed_kmh=None,
    ) -> Activity:
        activity = Activity(
            user_id=user_id,
            title=title,
            sport_type=sport_type,
            visibility=visibility,
            started_at=started_at,
            distance_m=distance_m,
            duration_s=duration_s,
            elevation_gain_m=elevation_gain_m,
            calories=calories,
            polyline=polyline,
            raw_file_path=raw_file_path,
            status=status,
            rank_eligible=rank_eligible,
            rank_excluded_reason=rank_excluded_reason,
            max_speed_kmh=max_speed_kmh,
        )
        self.db.add(activity)
        await self.db.flush()
        await self.db.refresh(activity)
        return activity

    async def update_raw_file_path(self, activity_id: UUID, raw_file_path: str) -> None:
        activity = await self.get_by_id(activity_id)
        if activity:
            activity.raw_file_path = raw_file_path
            await self.db.flush()

    async def get_feed(
        self,
        user_id: UUID,
        follower_ids: list[UUID],
        sport_type: ActivitySportType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Activity]:
        # Feed: own + followed, non-private, only ready activities
        q = select(Activity).where(
            Activity.status == ActivityStatus.READY,
            or_(
                Activity.user_id == user_id,
                and_(
                    Activity.user_id.in_(follower_ids),
                    Activity.visibility != ActivityVisibility.PRIVATE,
                ),
            ),
        )
        if sport_type:
            q = q.where(Activity.sport_type == sport_type)
        if date_from:
            q = q.where(Activity.started_at >= date_from)
        if date_to:
            q = q.where(Activity.started_at <= date_to)
        q = q.options(selectinload(Activity.user)).order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().unique().all())

    async def get_by_user_id(
        self, user_id: UUID, limit: int = 20, offset: int = 0, only_ready: bool = False
    ) -> list[Activity]:
        q = select(Activity).where(Activity.user_id == user_id)
        if only_ready:
            q = q.where(Activity.status == ActivityStatus.READY)
        q = (
            q.options(selectinload(Activity.user))
            .order_by(Activity.created_at.desc(), Activity.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(q)
        return list(result.scalars().unique().all())

    async def get_by_user_id_in_date_range(
        self, user_id: UUID, date_from: datetime, date_to: datetime
    ) -> list[Activity]:
        """READY activities for user with started_at in [date_from, date_to] (inclusive)."""
        q = (
            select(Activity)
            .where(Activity.user_id == user_id)
            .where(Activity.status == ActivityStatus.READY)
            .where(Activity.started_at >= date_from)
            .where(Activity.started_at <= date_to)
        )
        result = await self.db.execute(q)
        return list(result.scalars().unique().all())

    async def count_likes(self, activity_id: UUID) -> int:
        result = await self.db.execute(select(func.count(Like.id)).where(Like.activity_id == activity_id))
        return result.scalar() or 0
