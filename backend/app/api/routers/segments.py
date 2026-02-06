"""Segments: create, browse, detail, leaderboards, my efforts."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.models import Segment, SegmentEffort, Activity, ActivityVisibility, User
from app.schemas import (
    SegmentCreate,
    SegmentResponse,
    SegmentEffortResponse,
    SegmentLeaderboardItem,
    SegmentLeaderboardResponse,
)
from app.services.segments import decode_polyline_to_points, downsample_points, _haversine_m


router = APIRouter(prefix="/segments", tags=["segments"])


@router.post("", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(
    data: SegmentCreate,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SegmentResponse:
    # Decode polyline to estimate distance
    pts = decode_polyline_to_points(data.polyline)
    if len(pts) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Polyline must have at least 2 points")
    pts_ds = downsample_points(pts, max_points=200)
    distance_m = 0.0
    prev = pts_ds[0]
    for p in pts_ds[1:]:
        distance_m += _haversine_m(float(prev["lat"]), float(prev["lon"]), float(p["lat"]), float(p["lon"]))
        prev = p

    segment = Segment(
        owner_user_id=current_user_id,
        name=data.name,
        description=data.description,
        polyline=data.polyline,
        distance_m=distance_m,
        is_public=data.is_public,
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
    return SegmentResponse.model_validate(segment)


@router.get("", response_model=list[SegmentResponse])
async def list_segments(
    query: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[SegmentResponse]:
    stmt = select(Segment).where(Segment.is_public.is_(True))
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(Segment.name).like(like))
    stmt = stmt.order_by(Segment.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    segments = list(result.scalars().all())
    return [SegmentResponse.model_validate(s) for s in segments]


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: UUID,
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> SegmentResponse:
    result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
    if not segment.is_public and segment.owner_user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Segment is private")
    return SegmentResponse.model_validate(segment)


@router.get("/{segment_id}/leaderboard", response_model=SegmentLeaderboardResponse)
async def get_segment_leaderboard(
    segment_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> SegmentLeaderboardResponse:
    seg_result = await db.execute(select(Segment).where(Segment.id == segment_id))
    segment = seg_result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    # Public efforts only (visibility = public)
    effort_stmt = (
        select(
            SegmentEffort,
            User.name,
        )
        .join(Activity, Activity.id == SegmentEffort.activity_id)
        .join(User, User.id == Activity.user_id)
        .where(SegmentEffort.segment_id == segment_id)
        .where(SegmentEffort.visibility == ActivityVisibility.PUBLIC.value)
        .order_by(SegmentEffort.effort_time_s.asc())
        .limit(limit)
    )
    result = await db.execute(effort_stmt)
    rows = result.all()

    items: list[SegmentLeaderboardItem] = []
    best_time: int | None = None
    best_row: SegmentLeaderboardItem | None = None

    for effort, user_name in rows:
        item = SegmentLeaderboardItem(
            user_id=effort.user_id,
            name=user_name,
            activity_id=effort.activity_id,
            effort_time_s=effort.effort_time_s,
            effort_distance_m=effort.effort_distance_m,
            avg_speed_kmh=effort.avg_speed_kmh,
            started_at=effort.started_at,
            is_kom=False,
        )
        items.append(item)
        if best_time is None or effort.effort_time_s < best_time:
            best_time = effort.effort_time_s
            best_row = item

    kom_summary = None
    if best_row is not None and best_time is not None:
        best_row.is_kom = True
        kom_summary = {
            "user_id": best_row.user_id,
            "name": best_row.name,
            "activity_id": best_row.activity_id,
            "effort_time_s": best_row.effort_time_s,
            "started_at": best_row.started_at,
        }

    return SegmentLeaderboardResponse(segment=SegmentResponse.model_validate(segment), items=items, kom=kom_summary)


@router.get("/{segment_id}/my-efforts", response_model=list[SegmentEffortResponse])
async def get_my_segment_efforts(
    segment_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SegmentEffortResponse]:
    stmt = (
        select(SegmentEffort)
        .where(SegmentEffort.segment_id == segment_id)
        .where(SegmentEffort.user_id == current_user_id)
        .order_by(SegmentEffort.effort_time_s.asc())
    )
    result = await db.execute(stmt)
    efforts = list(result.scalars().all())
    # PR = best (first), and mark KOM if this effort matches global KOM among public efforts
    out: list[SegmentEffortResponse] = []
    # Compute global KOM (public efforts only)
    best_public_stmt = (
        select(func.min(SegmentEffort.effort_time_s))
        .where(SegmentEffort.segment_id == segment_id)
        .where(SegmentEffort.visibility == ActivityVisibility.PUBLIC.value)
    )
    best_public_result = await db.execute(best_public_stmt)
    best_public_time = best_public_result.scalar()

    out: list[SegmentEffortResponse] = []
    for idx, eff in enumerate(efforts):
        is_pr = idx == 0
        is_kom = bool(
            best_public_time is not None
            and eff.visibility == ActivityVisibility.PUBLIC.value
            and eff.effort_time_s == best_public_time
        )
        out.append(
            SegmentEffortResponse(
                id=eff.id,
                segment_id=eff.segment_id,
                activity_id=eff.activity_id,
                user_id=eff.user_id,
                effort_time_s=eff.effort_time_s,
                effort_distance_m=eff.effort_distance_m,
                avg_speed_kmh=eff.avg_speed_kmh,
                started_at=eff.started_at,
                visibility=eff.visibility,
                is_pr=is_pr,
                is_kom=is_kom,
            )
        )
    return out


