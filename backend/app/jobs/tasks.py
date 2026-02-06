"""RQ job: process uploaded GPX/TCX and update activity."""
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select, or_
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.models import Activity, TrackPoint, Segment, SegmentEffort, Notification
from app.models.activity import ActivityStatus, ActivitySportType, ActivityVisibility
from app.models.notification import NotificationType
from app.services.gpx_parser import (
    parse_gpx_tcx_to_track_points,
    compute_stats_from_points,
    encode_polyline_from_points,
)
from app.services.fairplay import compute_max_speed_kmh, is_suspicious_run
from app.services.segments import decode_polyline_to_points, match_segment, compute_effort_stats, downsample_points
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert


def _sync_engine():
    url = settings.database_url.replace("+asyncpg", "").replace("asyncpg", "psycopg2")
    if url.startswith("postgresql://") and "psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url, pool_pre_ping=True)


def _estimate_calories(sport_type: str, duration_s: int, distance_m: float) -> int:
    met = {"run": 10, "ride": 8, "walk": 3}.get(sport_type, 8)
    return int(met * 70 * (duration_s / 3600.0))


def process_activity_job(activity_id_str: str) -> None:
    """Parse raw file for activity and update stats/track points. Run in RQ worker."""
    activity_id = UUID(activity_id_str)
    engine = _sync_engine()
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    with SessionLocal() as session:  # type: Session
        activity = session.execute(select(Activity).where(Activity.id == activity_id)).scalar_one_or_none()
        if not activity or activity.status != ActivityStatus.PROCESSING or not activity.raw_file_path:
            return
        path = Path(activity.raw_file_path)
        if not path.is_file():
            activity.status = ActivityStatus.FAILED
            activity.error_message = "Upload file not found"
            session.commit()
            return
        try:
            content = path.read_bytes()
            ext = path.suffix.lower().lstrip(".")
            points = parse_gpx_tcx_to_track_points(content, path.name)
        except Exception as e:
            activity.status = ActivityStatus.FAILED
            activity.error_message = str(e)[:1000]
            session.commit()
            return
        if not points:
            activity.status = ActivityStatus.FAILED
            activity.error_message = "No track points in file"
            session.commit()
            return
        stats = compute_stats_from_points(points)
        distance_m = stats.get("distance_m")
        duration_s = stats.get("duration_s")
        elevation_gain_m = stats.get("elevation_gain_m")
        calories = _estimate_calories(activity.sport_type.value, duration_s or 0, float(distance_m or 0))
        polyline = encode_polyline_from_points(points)
        
        # FairPlay: compute max speed and check eligibility
        max_speed_kmh = compute_max_speed_kmh(points)
        activity.max_speed_kmh = max_speed_kmh
        
        if activity.sport_type == ActivitySportType.RUN:
            is_suspicious, reason = is_suspicious_run(distance_m, duration_s, max_speed_kmh)
            if is_suspicious:
                activity.rank_eligible = False
                activity.rank_excluded_reason = reason
            else:
                activity.rank_eligible = True
                activity.rank_excluded_reason = None
        else:
            # Non-RUN activities are eligible (not used in PaceRank anyway)
            activity.rank_eligible = True
            activity.rank_excluded_reason = None
        
        activity.distance_m = distance_m
        activity.duration_s = duration_s
        activity.elevation_gain_m = elevation_gain_m
        activity.calories = calories
        activity.polyline = polyline
        activity.status = ActivityStatus.READY
        activity.error_message = None
        for pt in points:
            tp = TrackPoint(
                activity_id=activity.id,
                time=pt["time"],
                lat=Decimal(str(pt["lat"])),
                lon=Decimal(str(pt["lon"])),
                elevation_m=Decimal(str(pt.get("elevation", 0) or 0)),
                cumulative_distance_m=pt.get("cumulative_distance_m"),
            )
            session.add(tp)

        # Segments: only for RUN activities that became READY
        if activity.sport_type == ActivitySportType.RUN and activity.status == ActivityStatus.READY:
            # Build simple points list (with time/lat/lon)
            act_points = [{"time": p["time"], "lat": float(p["lat"]), "lon": float(p["lon"])} for p in points]
            act_points_ds = downsample_points(act_points, max_points=500)

            # Load public segments (and segments owned by this user)
            seg_query = session.query(Segment).filter(
                or_(Segment.is_public.is_(True), Segment.owner_user_id == activity.user_id)
            )
            segments = seg_query.all()

            for seg in segments:
                seg_points = decode_polyline_to_points(seg.polyline)
                seg_points_ds = downsample_points(seg_points, max_points=200)
                match = match_segment(act_points_ds, seg_points_ds)
                if not match:
                    continue
                effort_time_s, effort_distance_m = compute_effort_stats(act_points_ds, match.start_idx, match.end_idx)
                if effort_time_s <= 0 or effort_distance_m <= 0:
                    continue
                avg_speed_kmh = (effort_distance_m / 1000.0) / (effort_time_s / 3600.0)
                # Avoid duplicate efforts for same (segment, activity)
                existing = (
                    session.query(SegmentEffort)
                    .filter(
                        SegmentEffort.segment_id == seg.id,
                        SegmentEffort.activity_id == activity.id,
                    )
                    .first()
                )
                if existing:
                    continue
                eff = SegmentEffort(
                    segment_id=seg.id,
                    activity_id=activity.id,
                    user_id=activity.user_id,
                    visibility=activity.visibility.value,
                    effort_time_s=effort_time_s,
                    effort_distance_m=effort_distance_m,
                    avg_speed_kmh=avg_speed_kmh,
                    started_at=activity.started_at,
                )
                session.add(eff)
                session.flush()  # Flush to get eff.id and ensure it's in DB for notification checks

                # Trigger PR/KOM notifications (sync version)
                _maybe_notify_segment_pr_sync(
                    session, activity.user_id, seg.id, seg.name, effort_time_s, activity.id
                )
                _maybe_notify_segment_kom_sync(
                    session, activity.user_id, seg.id, seg.name, effort_time_s, activity.id, activity.visibility.value
                )

        session.commit()


def _maybe_notify_segment_pr_sync(session, user_id, segment_id, segment_name, new_effort_time_s, activity_id):
    """Sync version for worker context."""
    # Get user's best effort_time_s for this segment
    best_time = (
        session.query(func.min(SegmentEffort.effort_time_s))
        .filter(SegmentEffort.user_id == user_id, SegmentEffort.segment_id == segment_id)
        .scalar()
    )
    if best_time is None or new_effort_time_s != best_time:
        return False

    # Get previous best (excluding this activity)
    prev_best = (
        session.query(func.min(SegmentEffort.effort_time_s))
        .filter(
            SegmentEffort.user_id == user_id,
            SegmentEffort.segment_id == segment_id,
            SegmentEffort.activity_id != activity_id,
        )
        .scalar()
    )
    if prev_best is not None and (prev_best - new_effort_time_s) < 1:
        return False

    dedupe_key = f"segment_pr:{user_id}:{segment_id}"
    stmt = (
        pg_insert(Notification)
        .values(
            recipient_user_id=user_id,
            actor_user_id=user_id,
            type=NotificationType.SEGMENT_PR,
            activity_id=activity_id,
            data={
                "segment_id": str(segment_id),
                "segment_name": segment_name,
                "activity_id": str(activity_id),
                "effort_time_s": new_effort_time_s,
                "type": "pr",
            },
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    session.execute(stmt)
    return True


def _maybe_notify_segment_kom_sync(session, user_id, segment_id, segment_name, new_effort_time_s, activity_id, activity_visibility):
    """Sync version for worker context."""
    if activity_visibility != ActivityVisibility.PUBLIC.value:
        return False

    best_public = (
        session.query(func.min(SegmentEffort.effort_time_s))
        .filter(
            SegmentEffort.segment_id == segment_id,
            SegmentEffort.visibility == ActivityVisibility.PUBLIC.value,
        )
        .scalar()
    )
    if best_public is None or new_effort_time_s != best_public:
        return False

    prev_best_public = (
        session.query(func.min(SegmentEffort.effort_time_s))
        .filter(
            SegmentEffort.segment_id == segment_id,
            SegmentEffort.visibility == ActivityVisibility.PUBLIC.value,
            SegmentEffort.activity_id != activity_id,
        )
        .scalar()
    )
    if prev_best_public is not None and (prev_best_public - new_effort_time_s) < 1:
        return False

    dedupe_key = f"segment_kom:{user_id}:{segment_id}"
    stmt = (
        pg_insert(Notification)
        .values(
            recipient_user_id=user_id,
            actor_user_id=user_id,
            type=NotificationType.SEGMENT_KOM,
            activity_id=activity_id,
            data={
                "segment_id": str(segment_id),
                "segment_name": segment_name,
                "activity_id": str(activity_id),
                "effort_time_s": new_effort_time_s,
                "type": "kom",
            },
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    session.execute(stmt)
    return True
