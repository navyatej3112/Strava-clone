"""Seed database with 5 users and 30 activities with realistic fake routes."""
import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from pathlib import Path

import polyline

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.database import Base
from app.models import User, Activity, Follow, Like, Comment, TrackPoint, Notification
from app.models.activity import ActivitySportType, ActivityVisibility
from app.models.notification import NotificationType


def make_fake_route(num_points: int = 20, center_lat: float = 37.77, center_lon: float = -122.42) -> list[tuple[float, float]]:
    """Generate a rough loop/out-and-back as (lat, lon) list."""
    points = []
    for i in range(num_points):
        # Random walk from center
        lat = center_lat + (random.random() - 0.5) * 0.05
        lon = center_lon + (random.random() - 0.5) * 0.05
        points.append((lat, lon))
    return points


def encode_route(points: list[tuple[float, float]]) -> str:
    return polyline.encode(points)


async def run():
    database_url = settings.database_url
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        # Don't create tables - assume migrations already ran
        pass

    async with async_session() as session:
        # Check existing users
        r = await session.execute(select(User).limit(1))
        if r.scalar_one_or_none():
            print("DB already has data; skipping seed.")
            return

        names = [
            ("Alex Runner", "Marathoner & trail enthusiast"),
            ("Jordan Cycle", "Road and gravel cyclist"),
            ("Sam Walker", "Daily walker, exploring the city"),
            ("Casey Pace", "5K to half marathon"),
            ("Riley Trail", "Mountain biker and hiker"),
        ]
        users = []
        for i, (name, bio) in enumerate(names):
            u = User(
                id=uuid4(),
                email=f"user{i+1}@pacetrail.demo",
                hashed_password=get_password_hash("password123"),
                name=name,
                bio=bio,
            )
            session.add(u)
            users.append(u)
        await session.flush()

        sport_types = [ActivitySportType.RUN, ActivitySportType.RIDE, ActivitySportType.WALK]
        titles_run = ["Morning run", "Lunch 5K", "Evening jog", "Trail run", "Interval session", "Long run", "Recovery run"]
        titles_ride = ["Commute", "Weekend ride", "Gravel loop", "Hill climb", "Coffee ride", "Century prep"]
        titles_walk = ["Morning walk", "Lunch walk", "Park stroll", "Hike", "City explore"]

        # user1=users[0], user2=users[1], user3=users[2]. user1 follows user2; user3 not followed by user1.
        # Activities spread over last 12 weeks with varied distances; user2 has followers-only and private.
        activities = []
        base_time = datetime.now(timezone.utc) - timedelta(weeks=12)
        for i in range(30):
            sport = random.choice(sport_types)
            if sport == ActivitySportType.RUN:
                title = random.choice(titles_run)
            elif sport == ActivitySportType.RIDE:
                title = random.choice(titles_ride)
            else:
                title = random.choice(titles_walk)
            # Spread over 12 weeks (84 days), varied so charts are non-flat
            started_at = base_time + timedelta(
                days=random.randint(0, 84),
                hours=random.randint(6, 19),
                minutes=random.randint(0, 59),
            )
            duration_s = random.randint(900, 7200)
            distance_m = Decimal(str(round(random.uniform(3000, 35000) / 1000) * 1000))
            elevation_gain_m = Decimal(str(round(random.uniform(0, 600), 1)))
            calories = random.randint(300, 1100)
            owner = random.choice(users)
            # user2 (index 1): mix of public, followers, private
            if owner.id == users[1].id:
                vis = random.choice([ActivityVisibility.PUBLIC, ActivityVisibility.PUBLIC, ActivityVisibility.FOLLOWERS, ActivityVisibility.PRIVATE])
            else:
                vis = random.choice([ActivityVisibility.PUBLIC, ActivityVisibility.PUBLIC, ActivityVisibility.FOLLOWERS])
            route = make_fake_route(random.randint(15, 40))
            polyline_str = encode_route(route)
            a = Activity(
                id=uuid4(),
                user_id=owner.id,
                title=title,
                sport_type=sport,
                visibility=vis,
                started_at=started_at,
                distance_m=distance_m,
                duration_s=duration_s,
                elevation_gain_m=elevation_gain_m,
                calories=calories,
                polyline=polyline_str,
            )
            session.add(a)
            activities.append(a)
        await session.flush()

        # Follows: user1 follows user2; plus 2–3 random others per user (no self, no duplicate)
        follow_pairs = {(users[0].id, users[1].id)}  # user1 follows user2
        for u in users:
            for _ in range(random.randint(2, 3)):
                other = random.choice(users)
                if other.id != u.id:
                    follow_pairs.add((u.id, other.id))
        for fid, fol_id in follow_pairs:
            session.add(Follow(follower_id=fid, followed_id=fol_id))
        await session.flush()

        for fid, fol_id in follow_pairs:
            session.add(
                Notification(
                    recipient_user_id=fol_id,
                    actor_user_id=fid,
                    type=NotificationType.FOLLOW,
                )
            )
        await session.flush()

        # Likes: random likes on activities (no duplicates)
        like_pairs = set()
        while len(like_pairs) < 50:
            u, a = random.choice(users), random.choice(activities)
            like_pairs.add((u.id, a.id))
        for uid, aid in like_pairs:
            session.add(Like(user_id=uid, activity_id=aid))
        await session.flush()

        activity_by_id = {a.id: a for a in activities}
        for uid, aid in like_pairs:
            act = activity_by_id.get(aid)
            if act and act.user_id != uid:
                session.add(
                    Notification(
                        recipient_user_id=act.user_id,
                        actor_user_id=uid,
                        type=NotificationType.LIKE,
                        activity_id=aid,
                    )
                )
        await session.flush()

        # Comments
        comments_text = ["Great pace!", "Nice route.", "Well done!", "Inspiring.", "Solid effort."]
        comments_list = []
        for _ in range(40):
            user = random.choice(users)
            activity = random.choice(activities)
            c = Comment(user_id=user.id, activity_id=activity.id, body=random.choice(comments_text))
            session.add(c)
            comments_list.append((c, user.id, activity.user_id, activity.id))
        await session.flush()

        for c, actor_id, recipient_id, act_id in comments_list:
            if actor_id != recipient_id:
                session.add(
                    Notification(
                        recipient_user_id=recipient_id,
                        actor_user_id=actor_id,
                        type=NotificationType.COMMENT,
                        activity_id=act_id,
                        comment_id=c.id,
                    )
                )

        # Ensure each user has at least one public READY RUN in last 30 days
        now = datetime.now(timezone.utc)
        recent_start = now - timedelta(days=30)
        for u in users:
            # Check if user already has a public run in range
            has_public_run = any(
                a.user_id == u.id
                and a.sport_type == ActivitySportType.RUN
                and a.visibility == ActivityVisibility.PUBLIC
                and recent_start <= a.started_at <= now
                for a in activities
            )
            if not has_public_run:
                started_at = recent_start + timedelta(days=random.randint(0, 29), hours=random.randint(6, 19))
                distance_m = Decimal(str(random.choice([3000, 5000, 8000, 10000])))
                duration_s = random.choice([20 * 60, 30 * 60, 45 * 60])
                elevation_gain_m = Decimal("100.0")
                calories = 500
                route = make_fake_route(random.randint(15, 30))
                polyline_str = encode_route(route)
                a = Activity(
                    id=uuid4(),
                    user_id=u.id,
                    title="Seeded public run",
                    sport_type=ActivitySportType.RUN,
                    visibility=ActivityVisibility.PUBLIC,
                    started_at=started_at,
                    distance_m=distance_m,
                    duration_s=duration_s,
                    elevation_gain_m=elevation_gain_m,
                    calories=calories,
                    polyline=polyline_str,
                )
                session.add(a)
                activities.append(a)

        # Ensure user1 follows at least 2 users (for following leaderboard)
        user1_follows = {fol_id for fid, fol_id in follow_pairs if fid == users[0].id}
        while len(user1_follows) < 2:
            other = random.choice([u for u in users if u.id != users[0].id])
            if other.id not in user1_follows:
                follow_pairs.add((users[0].id, other.id))
                session.add(Follow(follower_id=users[0].id, followed_id=other.id))
                user1_follows.add(other.id)
        await session.flush()

        # Recompute ranks for all users using existing RankService
        from app.services.rank_service import RankService
        from app.models.rank_snapshot import RankSnapshot
        from datetime import date

        rank_service = RankService(session)
        
        # For user1: temporarily set to bronze, then recompute to trigger rank_up
        user1 = users[0]
        old_tier = user1.rank_tier
        user1.rank_tier = "bronze"
        await session.flush()
        
        for u in users:
            await rank_service.recompute_user_rank(u.id, range_days=30)
        
        # Create snapshots for last 14 days for user1 and user2
        today = datetime.now(timezone.utc).date()
        for u in [users[0], users[1]]:
            current_score = float(u.rank_score or 0)
            for day_offset in range(14):
                snapshot_date = today - timedelta(days=day_offset)
                # Interpolate score from 0.6 * current to current with noise
                progress = 1.0 - (day_offset / 14.0)
                score = current_score * (0.6 + 0.4 * progress) + random.uniform(-5, 5)
                score = max(0, score)
                
                # Compute tier for this score
                from app.services.rank_service import score_to_tier
                tier, _, _ = score_to_tier(score)
                
                # Upsert private snapshot
                from sqlalchemy.dialects.postgresql import insert
                stmt_private = (
                    insert(RankSnapshot)
                    .values(
                        user_id=u.id,
                        snapshot_date=snapshot_date,
                        scope="private",
                        tier_id=tier.id,
                        tier_name=tier.name,
                        score=score,
                    )
                    .on_conflict_do_update(
                        constraint="uq_rank_snapshots_user_date_scope",
                        set_={
                            "tier_id": tier.id,
                            "tier_name": tier.name,
                            "score": score,
                        },
                    )
                )
                await session.execute(stmt_private)
                
                # Public snapshot (slightly lower score to simulate public-only)
                public_score = score * 0.85
                tier_public, _, _ = score_to_tier(public_score)
                stmt_public = (
                    insert(RankSnapshot)
                    .values(
                        user_id=u.id,
                        snapshot_date=snapshot_date,
                        scope="public",
                        tier_id=tier_public.id,
                        tier_name=tier_public.name,
                        score=public_score,
                    )
                    .on_conflict_do_update(
                        constraint="uq_rank_snapshots_user_date_scope",
                        set_={
                            "tier_id": tier_public.id,
                            "tier_name": tier_public.name,
                            "score": public_score,
                        },
                    )
                )
                await session.execute(stmt_public)
        
        await session.commit()

        # --- Segments seed: create a few segments that overlap existing runs ---
        print("Creating seed segments from existing runs...")
        from app.services.segments import decode_polyline_to_points, downsample_points, _haversine_m
        from app.models.segment import Segment
        from app.models.track_point import TrackPoint

        run_activities = [a for a in activities if a.sport_type == ActivitySportType.RUN and a.polyline]
        created_segments: list[Segment] = []
        max_segments = 3
        for a in run_activities[:max_segments]:
            try:
                pts = decode_polyline_to_points(a.polyline)
            except Exception:
                continue
            if len(pts) < 10:
                continue
            start_idx = len(pts) // 5
            end_idx = min(len(pts) - 1, start_idx + max(1, len(pts) // 3))
            window = pts[start_idx:end_idx]
            if len(window) < 2:
                continue
            window_ds = downsample_points(window, max_points=100)
            dist = 0.0
            prev = window_ds[0]
            for p in window_ds[1:]:
                dist += _haversine_m(float(prev["lat"]), float(prev["lon"]), float(p["lat"]), float(p["lon"]))
                prev = p
            if dist < 500:  # skip very short segments
                continue
            seg = Segment(
                id=uuid4(),
                owner_user_id=users[0].id,
                name=f"Seed Segment {len(created_segments) + 1}",
                description="Seeded demo segment",
                polyline=encode_route([(p["lat"], p["lon"]) for p in window_ds]),
                distance_m=float(dist),
            )
            session.add(seg)
            created_segments.append(seg)

        await session.flush()

        # --- Synthetic TrackPoints for some seeded runs to ensure efforts can be computed ---
        print("Creating synthetic track points for demo runs...")
        from random import uniform

        demo_runs = [a for a in run_activities if a.polyline][:5]
        for act in demo_runs:
            # Skip if track points already exist
            existing_tp = await session.execute(select(TrackPoint).where(TrackPoint.activity_id == act.id))
            if list(existing_tp.scalars().all()):
                continue
            try:
                pts = decode_polyline_to_points(act.polyline)
            except Exception:
                continue
            if len(pts) < 5:
                continue
            # Cap to 300 points
            pts_ds = downsample_points(pts, max_points=300)
            # Compute cumulative distance
            cumulative = [0.0]
            for i in range(1, len(pts_ds)):
                d = _haversine_m(
                    float(pts_ds[i - 1]["lat"]),
                    float(pts_ds[i - 1]["lon"]),
                    float(pts_ds[i]["lat"]),
                    float(pts_ds[i]["lon"]),
                )
                cumulative.append(cumulative[-1] + d)
            total_dist = cumulative[-1] or float(act.distance_m or 0)
            if total_dist <= 0:
                total_dist = float(act.distance_m or 5000)
            # Pace between ~4.5 and 7.0 min/km
            pace_min_per_km = uniform(4.5, 7.0)
            total_time_s = int((total_dist / 1000.0) * pace_min_per_km * 60)
            start_time = act.started_at
            for i, pt in enumerate(pts_ds):
                frac = cumulative[i] / total_dist if total_dist else 0
                t = start_time + timedelta(seconds=int(total_time_s * frac))
                tp = TrackPoint(
                    activity_id=act.id,
                    time=t,
                    lat=Decimal(str(pt["lat"])),
                    lon=Decimal(str(pt["lon"])),
                    elevation_m=None,
                    cumulative_distance_m=Decimal(str(round(cumulative[i], 2))),
                )
                session.add(tp)

        await session.flush()

        # --- Inline backfill for recent activities to guarantee demo efforts ---
        print("Backfilling segment efforts for recent runs...")
        # Import backfill function directly from the script file
        import importlib.util
        backfill_path = Path(__file__).parent / "backfill_segment_efforts.py"
        backfill_spec = importlib.util.spec_from_file_location("backfill_segment_efforts", backfill_path)
        backfill_module = importlib.util.module_from_spec(backfill_spec)
        backfill_spec.loader.exec_module(backfill_module)
        
        # Run backfill for the last 30 days, limited to 500 activities
        await backfill_module.backfill(30, 500, None)

        # Simple counts for demo: at least 3 segments and 2 segments with 3+ efforts
        seg_result = await session.execute(select(Segment))
        all_segments = list(seg_result.scalars().all())
        from app.models import SegmentEffort

        counts: dict[uuid4, int] = {}
        eff_result = await session.execute(select(SegmentEffort.segment_id, func.count(SegmentEffort.id)).group_by(SegmentEffort.segment_id))
        for seg_id, cnt in eff_result.all():
            counts[seg_id] = int(cnt)

        rich_segments = sum(1 for seg_id, cnt in counts.items() if cnt >= 3)

        await session.commit()
        print(
            f"Seeded 5 users, activities, follows, likes, comments, notifications, ranks, snapshots, rank_up notification, "
            f"{len(all_segments)} segments, and segment efforts (segments with >=3 efforts: {rich_segments})."
        )


if __name__ == "__main__":
    asyncio.run(run())
