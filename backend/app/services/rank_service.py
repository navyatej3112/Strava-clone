"""PaceRank: videogame-style ranks for runners.

Scoring is based on READY RUN activities in the last N days (default 30),
using distance, speed, elevation, and calories, plus a consistency bonus.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date
from typing import Iterable
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Activity, User, Follow, Notification, RankSnapshot
from app.models.activity import ActivitySportType, ActivityStatus, ActivityVisibility
from app.models.notification import NotificationType
from app.schemas import RankBreakdown, RankMeResponse


@dataclass(frozen=True)
class TierDef:
    id: str
    name: str
    min_score: float
    max_score: float | None  # None for top tier


TIERS: list[TierDef] = [
    TierDef(id="bronze", name="Bronze Trailblazer", min_score=0.0, max_score=40.0),
    TierDef(id="silver", name="Silver Strider", min_score=40.0, max_score=80.0),
    TierDef(id="gold", name="Gold Pacemaker", min_score=80.0, max_score=130.0),
    TierDef(id="platinum", name="Platinum Marathoner", min_score=130.0, max_score=190.0),
    TierDef(id="diamond", name="Diamond Elite", min_score=190.0, max_score=260.0),
    TierDef(id="world_class", name="World Class Legend", min_score=260.0, max_score=None),
]

# Tier ordering for rank-up detection
TIER_ORDER: dict[str, int] = {
    "bronze": 0,
    "silver": 1,
    "gold": 2,
    "platinum": 3,
    "diamond": 4,
    "world_class": 5,
}


def _today_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_run_score_30d(activities: Iterable[Activity]) -> tuple[float, RankBreakdown]:
    """Compute PaceRank score and breakdown for last-30d RUN activities."""
    runs_count = 0
    active_days: set[date] = set()
    total_distance_m = 0.0
    total_time_s = 0
    total_elev_m = 0.0
    total_calories = 0

    score_sum = 0.0

    for a in activities:
        if a.sport_type != ActivitySportType.RUN:
            continue
        if a.status != ActivityStatus.READY:
            continue
        # Filters: ignore very short runs
        if a.distance_m is None or a.duration_s is None:
            continue
        distance_m = float(a.distance_m)
        duration_s = int(a.duration_s)
        if distance_m < 1000 or duration_s < 300:
            continue

        runs_count += 1
        active_days.add(a.started_at.date())
        total_distance_m += distance_m
        total_time_s += duration_s
        elev_gain = float(a.elevation_gain_m or 0)
        total_elev_m += elev_gain
        calories = int(a.calories or 0)
        total_calories += calories

        distance_km = distance_m / 1000.0
        hours = max(duration_s, 1) / 3600.0
        speed_kmh = distance_km / hours if hours > 0 else 0.0

        elev_factor = 1.0 + min(elev_gain, 1200.0) / 2400.0
        calorie_factor = 1.0 + min(calories, 2500.0) / 5000.0
        speed_factor = max(0.6, min(speed_kmh / 10.0, 1.9))
        base = distance_km ** 0.75
        activity_points = base * speed_factor * elev_factor * calorie_factor
        score_sum += activity_points

    if total_time_s > 0:
        hours_total = total_time_s / 3600.0
        avg_speed_kmh = (total_distance_m / 1000.0) / hours_total
    else:
        avg_speed_kmh = 0.0

    active_days_count = len(active_days)
    consistency = 1.0 + min(runs_count, 20) / 40.0 + min(active_days_count, 20) / 50.0

    score = score_sum * consistency

    breakdown = RankBreakdown(
        runs_count=runs_count,
        active_days=active_days_count,
        total_distance_m=total_distance_m,
        total_time_s=total_time_s,
        avg_speed_kmh=avg_speed_kmh,
        total_elevation_gain_m=total_elev_m,
        total_calories=total_calories,
        score=score,
    )
    return score, breakdown


def score_to_tier(score: float) -> tuple[TierDef, TierDef | None, float]:
    """Map raw score to (tier, next_tier, progress 0..1)."""
    current: TierDef | None = None
    next_tier: TierDef | None = None
    for i, tier in enumerate(TIERS):
        if tier.max_score is None:
            # Top tier
            if score >= tier.min_score:
                current = tier
                next_tier = None
                break
        elif tier.min_score <= score < tier.max_score:
            current = tier
            next_tier = TIERS[i + 1] if i + 1 < len(TIERS) else None
            break
    if current is None:
        # Below bronze minimum, treat as bronze
        current = TIERS[0]
        next_tier = TIERS[1]

    if current.max_score is None:
        progress = 1.0
    else:
        span = current.max_score - current.min_score
        if span <= 0:
            progress = 1.0
        else:
            progress = max(0.0, min((score - current.min_score) / span, 1.0))
    return current, next_tier, progress


class RankService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_user_runs_last_n_days(self, user_id: UUID, range_days: int = 30) -> list[Activity]:
        now = _today_utc()
        date_from = now - timedelta(days=range_days)
        q = (
            select(Activity)
            .where(Activity.user_id == user_id)
            .where(Activity.status == ActivityStatus.READY)
            .where(Activity.sport_type == ActivitySportType.RUN)
            .where(Activity.rank_eligible == True)
            .where(Activity.started_at >= date_from)
            .where(Activity.started_at <= now)
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def recompute_user_rank(self, user_id: UUID, range_days: int = 30) -> RankMeResponse:
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        
        old_tier_id = user.rank_tier
        
        runs = await self._get_user_runs_last_n_days(user_id, range_days=range_days)
        score, breakdown = compute_run_score_30d(runs)
        tier, next_tier, progress = score_to_tier(score)

        user.rank_tier = tier.id
        user.rank_score = float(score)
        user.rank_range_days = range_days
        user.rank_last_computed_at = _today_utc()
        user.rank_progress = float(progress)
        user.rank_next_tier = next_tier.id if next_tier else None
        await self.db.flush()

        # Upsert today's private snapshot
        today = _today_utc().date()
        await self._upsert_snapshot(user_id, today, "private", tier.id, tier.name, float(score))
        
        # Compute and upsert public snapshot (viewer=None means public-only)
        public_rank = await self.compute_public_rank_for_viewer(user_id, viewer_id=None, range_days=range_days)
        await self._upsert_snapshot(user_id, today, "public", public_rank.rank_tier or "bronze", public_rank.rank_tier_name or "Bronze Trailblazer", public_rank.rank_score or 0.0)
        
        # Create rank-up notification if tier increased
        if old_tier_id and old_tier_id in TIER_ORDER and tier.id in TIER_ORDER:
            if TIER_ORDER[tier.id] > TIER_ORDER[old_tier_id]:
                await self._create_rank_up_notification(user_id, old_tier_id, tier.id, tier.name, float(score))
        
        await self.db.flush()

        return RankMeResponse(
            user_id=str(user.id),
            rank_tier=user.rank_tier,
            rank_tier_name=tier.name,
            rank_score=user.rank_score,
            rank_range_days=user.rank_range_days,
            rank_last_computed_at=user.rank_last_computed_at,
            rank_progress=user.rank_progress,
            rank_next_tier=user.rank_next_tier,
            breakdown=breakdown,
        )
    
    async def _upsert_snapshot(
        self, user_id: UUID, snapshot_date: date, scope: str, tier_id: str, tier_name: str, score: float
    ) -> None:
        """Upsert rank snapshot for user/date/scope."""
        from sqlalchemy.dialects.postgresql import insert
        
        stmt = (
            insert(RankSnapshot)
            .values(
                user_id=user_id,
                snapshot_date=snapshot_date,
                scope=scope,
                tier_id=tier_id,
                tier_name=tier_name,
                score=score,
            )
            .on_conflict_do_update(
                constraint="uq_rank_snapshots_user_date_scope",
                set_={
                    "tier_id": tier_id,
                    "tier_name": tier_name,
                    "score": score,
                    "created_at": _today_utc(),
                },
            )
        )
        await self.db.execute(stmt)
    
    async def _create_rank_up_notification(
        self, user_id: UUID, old_tier_id: str, new_tier_id: str, new_tier_name: str, score: float
    ) -> None:
        """Create rank-up notification."""
        n = Notification(
            recipient_user_id=user_id,
            actor_user_id=user_id,  # Self-notify
            type=NotificationType.RANK_UP,
            data={
                "old_tier": old_tier_id,
                "new_tier": new_tier_id,
                "new_tier_name": new_tier_name,
                "score": score,
            },
        )
        self.db.add(n)
    
    async def get_history_private(self, user_id: UUID, days: int = 30) -> list[RankSnapshot]:
        """Get private scope history for user."""
        now = _today_utc()
        date_from = now.date() - timedelta(days=days - 1)
        q = (
            select(RankSnapshot)
            .where(RankSnapshot.user_id == user_id)
            .where(RankSnapshot.scope == "private")
            .where(RankSnapshot.snapshot_date >= date_from)
            .order_by(RankSnapshot.snapshot_date.asc())
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())
    
    async def get_history_public(self, user_id: UUID, days: int = 30) -> list[RankSnapshot]:
        """Get public scope history for user."""
        now = _today_utc()
        date_from = now.date() - timedelta(days=days - 1)
        q = (
            select(RankSnapshot)
            .where(RankSnapshot.user_id == user_id)
            .where(RankSnapshot.scope == "public")
            .where(RankSnapshot.snapshot_date >= date_from)
            .order_by(RankSnapshot.snapshot_date.asc())
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def compute_public_rank_for_viewer(
        self,
        user_id: UUID,
        viewer_id: UUID | None,
        range_days: int = 30,
    ) -> RankMeResponse:
        """Compute rank for profile viewers, using only runs the viewer can see."""
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        now = _today_utc()
        date_from = now - timedelta(days=range_days)

        q = (
            select(Activity)
            .where(Activity.user_id == user_id)
            .where(Activity.status == ActivityStatus.READY)
            .where(Activity.sport_type == ActivitySportType.RUN)
            .where(Activity.rank_eligible == True)
            .where(Activity.started_at >= date_from)
            .where(Activity.started_at <= now)
        )

        visibility_filter = None
        if viewer_id is None or viewer_id == user_id:
            # Anonymous or owner: owner can see all; anonymous sees only public.
            if viewer_id is None:
                visibility_filter = Activity.visibility == ActivityVisibility.PUBLIC
        else:
            # Check if viewer follows this user
            follow_q = select(func.count(Follow.follower_id)).where(
                Follow.follower_id == viewer_id,
                Follow.followed_id == user_id,
            )
            res = await self.db.execute(follow_q)
            is_following = (res.scalar() or 0) > 0
            if is_following:
                visibility_filter = Activity.visibility.in_(
                    [ActivityVisibility.PUBLIC, ActivityVisibility.FOLLOWERS]
                )
            else:
                visibility_filter = Activity.visibility == ActivityVisibility.PUBLIC

        if visibility_filter is not None:
            q = q.where(visibility_filter)

        result = await self.db.execute(q)
        activities = list(result.scalars().all())

        score, breakdown = compute_run_score_30d(activities)
        tier, next_tier, progress = score_to_tier(score)

        return RankMeResponse(
            user_id=str(user.id),
            rank_tier=tier.id,
            rank_tier_name=tier.name,
            rank_score=float(score),
            rank_range_days=range_days,
            rank_last_computed_at=now,
            rank_progress=float(progress),
            rank_next_tier=next_tier.id if next_tier else None,
            breakdown=None,
        )

    async def maybe_recompute_if_stale(self, user_id: UUID, range_days: int = 30, stale_hours: int = 6) -> RankMeResponse:
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        now = _today_utc()
        stale = (
            user.rank_last_computed_at is None
            or user.rank_range_days != range_days
            or (now - user.rank_last_computed_at) >= timedelta(hours=stale_hours)
        )
        if stale:
            return await self.recompute_user_rank(user_id, range_days=range_days)

        # Return current values with no recompute
        # We don't recompute breakdown here (to keep it cheap); API can treat breakdown as optional.
        return RankMeResponse(
            user_id=str(user.id),
            rank_tier=user.rank_tier,
            rank_tier_name=self._tier_name(user.rank_tier),
            rank_score=user.rank_score,
            rank_range_days=user.rank_range_days or range_days,
            rank_last_computed_at=user.rank_last_computed_at,
            rank_progress=user.rank_progress,
            rank_next_tier=user.rank_next_tier,
            breakdown=None,
        )

    def _tier_name(self, tier_id: str | None) -> str | None:
        if tier_id is None:
            return None
        for t in TIERS:
            if t.id == tier_id:
                return t.name
        return None

