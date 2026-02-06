"""PaceRank API: ranks and leaderboards."""
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.core.cache import get_cached, set_cached
from app.core.queue import get_queue
from app.models import User, Activity, Follow
from app.models.activity import ActivitySportType, ActivityStatus, ActivityVisibility
from app.schemas import (
    RankMeResponse,
    TierInfo,
    RunLeaderboardResponse,
    RunLeaderboardItem,
    RankHistoryResponse,
    RankSnapshotItem,
)
from app.services.rank_service import RankService, TIERS

router = APIRouter(prefix="/ranks", tags=["ranks"])


@router.get("/me", response_model=RankMeResponse)
async def get_my_rank(
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RankMeResponse:
    service = RankService(db)
    try:
        return await service.maybe_recompute_if_stale(current_user_id, range_days=30, stale_hours=6)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.post("/me/recompute")
async def recompute_my_rank(
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enqueue rank recompute job. Returns job_id for polling."""
    queue = get_queue()
    if not queue:
        # Fallback: synchronous recompute if Redis unavailable
        service = RankService(db)
        try:
            resp = await service.recompute_user_rank(current_user_id, range_days=30)
            await db.commit()
            return {"status": "finished", "result": resp.model_dump()}
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    from app.jobs.rank_tasks import recompute_rank_job
    job = queue.enqueue(recompute_rank_job, str(current_user_id), 30)
    return {"status": "queued", "job_id": job.id}


@router.get("/me/recompute/{job_id}")
async def get_recompute_status(
    job_id: str,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get status of rank recompute job."""
    from rq import Job
    from rq.job import NoSuchJobError
    
    try:
        job = Job.fetch(job_id, connection=get_queue().connection)
        job_status = job.get_status()
        
        if job_status == "finished":
            result = job.result
            if result and "error" not in result:
                # Return RankMeResponse-like structure
                return {
                    "status": "finished",
                    "result": {
                        "user_id": str(current_user_id),
                        "rank_tier": result.get("tier"),
                        "rank_score": result.get("score"),
                        "rank_progress": result.get("progress"),
                        "rank_next_tier": result.get("next_tier"),
                        "rank_last_computed_at": result.get("last_computed_at"),
                    },
                }
            else:
                return {"status": "failed", "error": result.get("error", "Unknown error") if result else "Job failed"}
        elif job_status == "failed":
            return {"status": "failed", "error": str(job.exc_info) if job.exc_info else "Job failed"}
        else:
            return {"status": job_status}
    except NoSuchJobError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


@router.get("/tiers", response_model=list[TierInfo])
async def get_tiers() -> list[TierInfo]:
    items: list[TierInfo] = []
    for t in TIERS:
        items.append(
            TierInfo(
                id=t.id,
                name=t.name,
                min_score=t.min_score,
                max_score=t.max_score,
            )
        )
    return items


@router.get("/leaderboards/runs", response_model=RunLeaderboardResponse)
async def get_run_leaderboard(
    range: str = Query("30d", alias="range"),
    limit: int = Query(50, ge=1, le=200),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> RunLeaderboardResponse:
    """Leaderboard based on rank_score, only users with at least 1 public READY run in range."""
    if range not in ("30d",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only 30d range is currently supported")
    
    # Try cache
    cache_key = f"leaderboard:global:30d:limit={limit}"
    cached = await get_cached(cache_key)
    if cached:
        return RunLeaderboardResponse(**cached)
    
    range_days = 30
    now = datetime.now(timezone.utc)
    date_from = now - timedelta(days=range_days)

    # Fetch public READY run stats per user in one query.
    stmt = (
        select(
            User.id.label("user_id"),
            User.name.label("name"),
            User.rank_tier,
            User.rank_score,
            func.count(Activity.id).label("runs_count"),
            func.coalesce(func.sum(Activity.distance_m), 0).label("total_distance_m"),
        )
        .select_from(Activity)
        .join(User, User.id == Activity.user_id)
        .where(Activity.status == ActivityStatus.READY)
        .where(Activity.sport_type == ActivitySportType.RUN)
        .where(Activity.visibility == ActivityVisibility.PUBLIC)
        .where(Activity.rank_eligible == True)
        .where(Activity.started_at >= date_from)
        .where(Activity.started_at <= now)
        .group_by(User.id, User.name, User.rank_tier, User.rank_score)
    )
    result = await db.execute(stmt)
    rows = result.all()

    def tier_name(tier_id: str | None) -> str | None:
        if tier_id is None:
            return None
        from app.services.rank_service import TIERS as _TIERS

        for t in _TIERS:
            if t.id == tier_id:
                return t.name
        return None

    items: list[RunLeaderboardItem] = []
    for row in rows:
        runs_count = int(row.runs_count or 0)
        if runs_count <= 0:
            continue
        total_distance_m = float(row.total_distance_m or 0)
        tier = row.rank_tier
        items.append(
            RunLeaderboardItem(
                user_id=str(row.user_id),
                name=row.name,
                rank_tier=tier,
                rank_tier_name=tier_name(tier),
                rank_score=float(row.rank_score) if row.rank_score is not None else None,
                runs_count_public=runs_count,
                total_distance_public_m=total_distance_m,
            )
        )

    # Sort by rank_score desc (None last), then total_distance_public_m desc.
    def sort_key(item: RunLeaderboardItem):
        score = item.rank_score if item.rank_score is not None else -1e9
        return (-score, -item.total_distance_public_m)

    items_sorted = sorted(items, key=sort_key)[:limit]
    resp = RunLeaderboardResponse(range_days=range_days, items=items_sorted)
    
    # Cache response
    await set_cached(cache_key, resp.model_dump(), ttl=60)
    
    return resp


@router.get("/users/{user_id}", response_model=RankMeResponse)
async def get_user_rank_public(
    user_id: UUID,
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> RankMeResponse:
    """Public-facing rank for a user, using only viewable runs for the requester."""
    service = RankService(db)
    try:
        return await service.compute_public_rank_for_viewer(user_id=user_id, viewer_id=current_user_id, range_days=30)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("/me/history", response_model=RankHistoryResponse)
async def get_my_history(
    days: int = Query(30, ge=1, le=365),
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RankHistoryResponse:
    """Get private scope rank history for current user."""
    service = RankService(db)
    snapshots = await service.get_history_private(current_user_id, days=days)
    items = [
        RankSnapshotItem(
            date=s.snapshot_date.isoformat(),
            tier_id=s.tier_id,
            tier_name=s.tier_name,
            score=s.score,
        )
        for s in snapshots
    ]
    return RankHistoryResponse(
        user_id=str(current_user_id),
        scope="private",
        days=days,
        items=items,
    )


@router.get("/users/{user_id}/history", response_model=RankHistoryResponse)
async def get_user_history(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> RankHistoryResponse:
    """Get rank history for a user. Private scope if viewer is owner, else public scope."""
    service = RankService(db)
    scope = "private" if current_user_id == user_id else "public"
    if scope == "private":
        snapshots = await service.get_history_private(user_id, days=days)
    else:
        snapshots = await service.get_history_public(user_id, days=days)
    items = [
        RankSnapshotItem(
            date=s.snapshot_date.isoformat(),
            tier_id=s.tier_id,
            tier_name=s.tier_name,
            score=s.score,
        )
        for s in snapshots
    ]
    return RankHistoryResponse(
        user_id=str(user_id),
        scope=scope,
        days=days,
        items=items,
    )


@router.get("/leaderboards/runs/following", response_model=RunLeaderboardResponse)
async def get_run_leaderboard_following(
    range: str = Query("30d", alias="range"),
    limit: int = Query(50, ge=1, le=200),
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunLeaderboardResponse:
    """Leaderboard of users that current user follows (plus optionally self)."""
    if range not in ("30d",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only 30d range is currently supported")
    
    # Try cache
    cache_key = f"leaderboard:following:{current_user_id}:30d:limit={limit}"
    cached = await get_cached(cache_key)
    if cached:
        return RunLeaderboardResponse(**cached)
    
    range_days = 30
    now = datetime.now(timezone.utc)
    date_from = now - timedelta(days=range_days)
    
    # Get followed user IDs
    follow_q = select(Follow.followed_id).where(Follow.follower_id == current_user_id)
    follow_result = await db.execute(follow_q)
    followed_ids = [row[0] for row in follow_result.all()]
    followed_ids.append(current_user_id)  # Include self
    
    if not followed_ids:
        return RunLeaderboardResponse(range_days=range_days, items=[])
    
    # Fetch public READY run stats per user in one query, filtered to followed users
    stmt = (
        select(
            User.id.label("user_id"),
            User.name.label("name"),
            User.rank_tier,
            User.rank_score,
            func.count(Activity.id).label("runs_count"),
            func.coalesce(func.sum(Activity.distance_m), 0).label("total_distance_m"),
        )
        .select_from(Activity)
        .join(User, User.id == Activity.user_id)
        .where(Activity.status == ActivityStatus.READY)
        .where(Activity.sport_type == ActivitySportType.RUN)
        .where(Activity.visibility == ActivityVisibility.PUBLIC)
        .where(Activity.rank_eligible == True)
        .where(Activity.started_at >= date_from)
        .where(Activity.started_at <= now)
        .where(User.id.in_(followed_ids))
        .group_by(User.id, User.name, User.rank_tier, User.rank_score)
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    def tier_name(tier_id: str | None) -> str | None:
        if tier_id is None:
            return None
        from app.services.rank_service import TIERS as _TIERS
        
        for t in _TIERS:
            if t.id == tier_id:
                return t.name
        return None
    
    items: list[RunLeaderboardItem] = []
    for row in rows:
        runs_count = int(row.runs_count or 0)
        if runs_count <= 0:
            continue
        total_distance_m = float(row.total_distance_m or 0)
        tier = row.rank_tier
        items.append(
            RunLeaderboardItem(
                user_id=str(row.user_id),
                name=row.name,
                rank_tier=tier,
                rank_tier_name=tier_name(tier),
                rank_score=float(row.rank_score) if row.rank_score is not None else None,
                runs_count_public=runs_count,
                total_distance_public_m=total_distance_m,
            )
        )
    
    # Sort by rank_score desc (None last), then total_distance_public_m desc.
    def sort_key(item: RunLeaderboardItem):
        score = item.rank_score if item.rank_score is not None else -1e9
        return (-score, -item.total_distance_public_m)
    
    items_sorted = sorted(items, key=sort_key)[:limit]
    resp = RunLeaderboardResponse(range_days=range_days, items=items_sorted)
    
    # Cache response
    await set_cached(cache_key, resp.model_dump(), ttl=60)
    
    return resp
