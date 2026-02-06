"""Activity CRUD and stats computation."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func

from app.models import Activity, Like, Comment, TrackPoint, Segment
from app.models.activity import ActivitySportType, ActivityVisibility, ActivityStatus
from app.repositories.activity_repository import ActivityRepository
from app.schemas import (
    ActivityCreate,
    ActivityUpdate,
    ActivityResponse,
    ActivityListResponse,
    SportType,
    Visibility,
    ActivityStatus as SchemaActivityStatus,
    SplitResponse,
    ElevationPoint,
    UserPublic,
    SegmentEffortResponse,
)
from app.services.gpx_parser import parse_gpx_tcx_to_track_points, compute_stats_from_points, encode_polyline_from_points
from app.services.fairplay import is_suspicious_run


class ActivityService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ActivityRepository(db)

    def _sport_type_to_enum(self, s: SportType) -> ActivitySportType:
        return ActivitySportType(s.value)

    def _visibility_to_enum(self, v: Visibility) -> ActivityVisibility:
        return ActivityVisibility(v.value)

    async def create(
        self,
        user_id: UUID,
        data: ActivityCreate,
        *,
        track_points_from_file: list[dict] | None = None,
        create_processing: bool = False,
    ) -> ActivityResponse:
        sport_type = self._sport_type_to_enum(data.sport_type)
        visibility = self._visibility_to_enum(data.visibility)
        distance_m = data.distance_m
        duration_s = data.duration_s
        elevation_gain_m = data.elevation_gain_m
        calories = data.calories
        polyline = data.polyline
        if create_processing:
            # File will be processed by background job; create with minimal fields
            activity = await self.repo.create(
                user_id=user_id,
                title=data.title,
                sport_type=sport_type,
                visibility=visibility,
                started_at=data.started_at,
                distance_m=None,
                duration_s=None,
                elevation_gain_m=None,
                calories=None,
                polyline=None,
                raw_file_path=None,
                status=ActivityStatus.PROCESSING,
            )
            await self.db.commit()
            await self.db.refresh(activity)
            return await self.get_by_id(activity.id, current_user_id=user_id)
        max_speed_kmh = None
        if track_points_from_file:
            points = track_points_from_file
            stats = compute_stats_from_points(points)
            distance_m = stats.get("distance_m") or distance_m
            duration_s = stats.get("duration_s") or duration_s
            elevation_gain_m = stats.get("elevation_gain_m") or elevation_gain_m
            if calories is None and duration_s and distance_m:
                calories = self._estimate_calories(sport_type, float(duration_s or 0), float(distance_m or 0))
            polyline = polyline or encode_polyline_from_points(points)
            # Compute max speed from points
            from app.services.fairplay import compute_max_speed_kmh as _compute_max
            max_speed_kmh = _compute_max(points)
        elif data.polyline and (distance_m is None or duration_s is None):
            pass
        
        if calories is None and duration_s and distance_m:
            calories = self._estimate_calories(sport_type, int(duration_s or 0), float(distance_m or 0))
        
        # FairPlay check for RUN activities
        rank_eligible = True
        rank_excluded_reason = None
        if sport_type == ActivitySportType.RUN:
            is_suspicious, reason = is_suspicious_run(distance_m, duration_s, max_speed_kmh)
            if is_suspicious:
                rank_eligible = False
                rank_excluded_reason = reason
        
        activity = await self.repo.create(
            user_id=user_id,
            title=data.title,
            sport_type=sport_type,
            visibility=visibility,
            started_at=data.started_at,
            distance_m=distance_m,
            duration_s=duration_s,
            elevation_gain_m=elevation_gain_m,
            calories=calories,
            polyline=polyline,
            rank_eligible=rank_eligible,
            rank_excluded_reason=rank_excluded_reason,
            max_speed_kmh=max_speed_kmh,
        )
        if track_points_from_file:
            for pt in track_points_from_file:
                tp = TrackPoint(
                    activity_id=activity.id,
                    time=pt["time"],
                    lat=Decimal(str(pt["lat"])),
                    lon=Decimal(str(pt["lon"])),
                    elevation_m=Decimal(str(pt.get("elevation", 0) or 0)),
                    cumulative_distance_m=pt.get("cumulative_distance_m"),
                )
                self.db.add(tp)
        await self.db.commit()
        await self.db.refresh(activity)
        return await self.get_by_id(activity.id, current_user_id=user_id)

    def _estimate_calories(self, sport_type: ActivitySportType, duration_s: int, distance_m: float) -> int:
        # Simple estimate: MET-based rough calc (e.g. run ~10 MET, ride ~8 MET, walk ~3 MET)
        met = {"run": 10, "ride": 8, "walk": 3}.get(sport_type.value, 8)
        # calories ≈ MET * weight_kg * hours; assume 70kg
        hours = duration_s / 3600.0
        return int(met * 70 * hours)

    async def get_by_id(self, activity_id: UUID, current_user_id: UUID | None = None) -> ActivityResponse | None:
        activity = await self.repo.get_by_id(activity_id, load_user=True)
        if not activity:
            return None
        like_count = await self.repo.count_likes(activity_id)
        result = await self.db.execute(select(func.count(Comment.id)).where(Comment.activity_id == activity_id))
        comment_count = result.scalar() or 0
        liked_by_me = False
        if current_user_id:
            r = await self.db.execute(select(Like).where(Like.activity_id == activity_id, Like.user_id == current_user_id))
            liked_by_me = r.scalar_one_or_none() is not None
        user_public = UserPublic.model_validate(activity.user) if activity.user else None
        splits = await self._get_splits(activity_id)
        elevation_profile = await self._get_elevation_profile(activity_id)
        segments = await self._get_segment_efforts(activity_id, activity.user_id)
        return ActivityResponse(
            id=activity.id,
            user_id=activity.user_id,
            title=activity.title,
            sport_type=SportType(activity.sport_type.value),
            visibility=Visibility(activity.visibility.value),
            started_at=activity.started_at,
            distance_m=activity.distance_m,
            duration_s=activity.duration_s,
            elevation_gain_m=activity.elevation_gain_m,
            calories=activity.calories,
            polyline=activity.polyline,
            created_at=activity.created_at,
            like_count=like_count,
            comment_count=comment_count,
            liked_by_me=liked_by_me,
            user=user_public,
            splits=splits,
            elevation_profile=elevation_profile,
            status=SchemaActivityStatus(activity.status.value),
            error_message=activity.error_message,
            rank_eligible=activity.rank_eligible,
            rank_excluded_reason=activity.rank_excluded_reason,
            max_speed_kmh=activity.max_speed_kmh,
            segments=segments,
        )

    async def _get_splits(self, activity_id: UUID) -> list[SplitResponse]:
        # Per-km splits from track points (simplified: from stored points if available)
        points = await self.db.execute(
            select(TrackPoint).where(TrackPoint.activity_id == activity_id).order_by(TrackPoint.time)
        )
        pts = list(points.scalars().all())
        if len(pts) < 2:
            return []
        splits = []
        segment_distance = 1000  # 1 km
        current_segment_m = 0
        segment_start_time = pts[0].time
        segment_start_dist = 0
        for i in range(1, len(pts)):
            # Approximate distance between consecutive points (Haversine simplified or use cumulative_distance_m)
            if pts[i].cumulative_distance_m is not None:
                dist = float(pts[i].cumulative_distance_m) - segment_start_dist
            else:
                dist = 0  # skip if no cumulative
            current_segment_m += dist
            if current_segment_m >= segment_distance:
                dur = (pts[i].time - segment_start_time).total_seconds()
                splits.append(
                    SplitResponse(
                        index=len(splits) + 1,
                        distance_m=Decimal(segment_distance),
                        duration_s=int(dur),
                        pace_per_km_s=float(dur) / (segment_distance / 1000) if segment_distance else None,
                        speed_kmh=(segment_distance / 1000) / (dur / 3600) if dur else None,
                    )
                )
                segment_start_time = pts[i].time
                segment_start_dist = float(pts[i].cumulative_distance_m or 0)
                current_segment_m = 0
        return splits

    async def _get_elevation_profile(self, activity_id: UUID) -> list[ElevationPoint]:
        result = await self.db.execute(
            select(TrackPoint).where(TrackPoint.activity_id == activity_id).order_by(TrackPoint.time)
        )
        pts = result.scalars().all()
        out = []
        for p in pts:
            out.append(
                ElevationPoint(
                    distance_m=p.cumulative_distance_m or Decimal(0),
                    elevation_m=p.elevation_m or Decimal(0),
                    time_iso=p.time.isoformat() if p.time else None,
                )
            )
        return out

    async def _get_segment_efforts(self, activity_id: UUID, owner_user_id: UUID) -> list[SegmentEffortResponse]:
        """Return segment efforts for this activity, marking PRs for the activity owner."""
        from app.models import SegmentEffort

        result = await self.db.execute(
            select(SegmentEffort).where(SegmentEffort.activity_id == activity_id).order_by(SegmentEffort.effort_time_s)
        )
        efforts = list(result.scalars().all())
        if not efforts:
            return []

        # Load segment names
        segment_ids = {e.segment_id for e in efforts}
        segment_names: dict[UUID, str] = {}
        if segment_ids:
            seg_result = await self.db.execute(select(Segment.id, Segment.name).where(Segment.id.in_(segment_ids)))
            for seg_id, name in seg_result.all():
                segment_names[seg_id] = name

        # Compute best time per segment for the owner
        best_times: dict[UUID, int] = {}
        if segment_ids:
            best_stmt = (
                select(SegmentEffort.segment_id, func.min(SegmentEffort.effort_time_s))
                .where(SegmentEffort.user_id == owner_user_id)
                .where(SegmentEffort.segment_id.in_(segment_ids))
                .group_by(SegmentEffort.segment_id)
            )
            best_result = await self.db.execute(best_stmt)
            for seg_id, min_time in best_result.all():
                best_times[seg_id] = int(min_time)

        out: list[SegmentEffortResponse] = []
        for e in efforts:
            best = best_times.get(e.segment_id)
            is_pr = bool(best is not None and e.user_id == owner_user_id and e.effort_time_s == best)
            out.append(
                SegmentEffortResponse(
                    id=e.id,
                    segment_id=e.segment_id,
                    activity_id=e.activity_id,
                    user_id=e.user_id,
                    segment_name=segment_names.get(e.segment_id),
                    effort_time_s=e.effort_time_s,
                    effort_distance_m=e.effort_distance_m,
                    avg_speed_kmh=e.avg_speed_kmh,
                    started_at=e.started_at,
                    visibility=e.visibility,
                    is_pr=is_pr,
                )
            )
        return out

    async def update(self, activity_id: UUID, user_id: UUID, data: ActivityUpdate) -> ActivityResponse | None:
        activity = await self.repo.get_by_id(activity_id)
        if not activity or activity.user_id != user_id:
            return None
        updates = data.model_dump(exclude_unset=True)
        if "visibility" in updates:
            updates["visibility"] = self._visibility_to_enum(updates["visibility"])
        for k, v in updates.items():
            setattr(activity, k, v)
        await self.db.commit()
        await self.db.refresh(activity)
        return await self.get_by_id(activity_id, current_user_id=user_id)

    async def delete(self, activity_id: UUID, user_id: UUID) -> bool:
        activity = await self.repo.get_by_id(activity_id)
        if not activity or activity.user_id != user_id:
            return False
        await self.db.delete(activity)
        await self.db.commit()
        return True
