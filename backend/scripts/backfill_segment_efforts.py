"""Backfill segment efforts for recent activities.

Usage:

    python -m scripts.backfill_segment_efforts --days 30
"""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, or_  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models import Activity, Segment, SegmentEffort, ActivitySportType, ActivityStatus, TrackPoint  # noqa: E402
from app.models.activity import ActivityVisibility  # noqa: E402
from app.services.segments import (
    downsample_points,
    match_segment,
    compute_effort_stats,
    trackpoints_to_points,
)  # noqa: E402
from app.services.segment_notifications import maybe_notify_segment_pr, maybe_notify_segment_kom  # noqa: E402


async def backfill(days: int, limit_activities: int, segment_ids: list[str] | None = None) -> None:
    """Scan READY RUN activities in the last N days and (re)create segment efforts."""
    database_url = settings.database_url
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    async with async_session() as session:
        seg_stmt = select(Segment)
        if segment_ids:
            from uuid import UUID

            seg_ids_uuid = [UUID(sid) for sid in segment_ids]
            seg_stmt = seg_stmt.where(Segment.id.in_(seg_ids_uuid))
        seg_result = await session.execute(seg_stmt)
        segments = list(seg_result.scalars().all())
        if not segments:
            print("No segments found; nothing to backfill.")
            return

        act_stmt = (
            select(Activity)
            .where(Activity.status == ActivityStatus.READY)
            .where(Activity.sport_type == ActivitySportType.RUN)
            .where(Activity.started_at >= start)
            .where(Activity.started_at <= now)
            .order_by(Activity.started_at.desc())
            .limit(limit_activities)
        )
        acts_result = await session.execute(act_stmt)
        activities = list(acts_result.scalars().all())
        if not activities:
            print("No READY RUN activities found in range; nothing to backfill.")
            return

        scanned = 0
        inserted = 0
        skipped_existing = 0
        matched_segments = 0

        from sqlalchemy import select as sa_select

        for act in activities:
            scanned += 1
            # Load trackpoints with timestamps
            tp_result = await session.execute(
                sa_select(TrackPoint).where(TrackPoint.activity_id == act.id).order_by(TrackPoint.time)
            )
            tps = list(tp_result.scalars().all())
            if len(tps) < 10:
                continue
            points = trackpoints_to_points(tps)
            if len(points) < 10:
                continue
            points_ds = downsample_points(points, max_points=500)

            # Segments to consider: public + owner segments (further filtered if segment_ids provided above)
            seg_for_activity = [
                s
                for s in segments
                if s.is_public or s.owner_user_id == act.user_id
            ]
            if not seg_for_activity:
                continue

            for seg in seg_for_activity:
                seg_points_raw = trackpoints_to_points(
                    []  # placeholder to satisfy type; we'll decode from polyline below
                )
                # Decode segment polyline into points
                from app.services.segments import decode_polyline_to_points

                try:
                    seg_pts = decode_polyline_to_points(seg.polyline)
                except Exception:
                    continue
                if len(seg_pts) < 2:
                    continue
                seg_pts_ds = downsample_points(seg_pts, max_points=200)
                match = match_segment(points_ds, seg_pts_ds)
                if not match:
                    continue

                effort_time_s, effort_distance_m = compute_effort_stats(points_ds, match.start_idx, match.end_idx)
                if effort_time_s <= 0 or effort_distance_m <= 0:
                    continue

                # Check existing
                existing = await session.execute(
                    sa_select(SegmentEffort).where(
                        SegmentEffort.segment_id == seg.id,
                        SegmentEffort.activity_id == act.id,
                    )
                )
                if existing.scalar_one_or_none():
                    skipped_existing += 1
                    continue

                avg_speed_kmh = (effort_distance_m / 1000.0) / (effort_time_s / 3600.0)
                eff = SegmentEffort(
                    segment_id=seg.id,
                    activity_id=act.id,
                    user_id=act.user_id,
                    visibility=act.visibility.value,
                    effort_time_s=effort_time_s,
                    effort_distance_m=effort_distance_m,
                    avg_speed_kmh=avg_speed_kmh,
                    started_at=act.started_at,
                )
                session.add(eff)
                await session.flush()  # Flush to ensure effort is in DB for notification checks

                # Trigger PR/KOM notifications
                await maybe_notify_segment_pr(
                    session, act.user_id, seg.id, seg.name, effort_time_s, act.id
                )
                await maybe_notify_segment_kom(
                    session, act.user_id, seg.id, seg.name, effort_time_s, act.id, act.visibility.value
                )

                inserted += 1
                matched_segments += 1

        await session.commit()
        print(
            f"Scanned {scanned} activities, segments matched: {matched_segments}, "
            f"inserted efforts: {inserted}, skipped existing: {skipped_existing}."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="How many days back to scan")
    parser.add_argument("--limit-activities", type=int, default=500, help="Max activities to scan")
    parser.add_argument(
        "--segment-ids",
        type=str,
        default="",
        help="Comma-separated list of segment UUIDs to restrict backfill to",
    )
    args = parser.parse_args()
    seg_ids = [s for s in args.segment_ids.split(",") if s] if args.segment_ids else None
    asyncio.run(backfill(args.days, args.limit_activities, seg_ids))


if __name__ == "__main__":
  main()

