"""Activities: create, get, update, delete, list by user; file upload."""
from pathlib import Path
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.queue import get_queue
from app.services.activity_service import ActivityService
from app.schemas import ActivityCreate, ActivityUpdate, ActivityResponse, ActivityListResponse, SportType
from app.api.deps import get_current_user, get_current_user_optional, rate_limit_stub
from app.services.gpx_parser import parse_gpx_tcx_to_track_points

router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    request: Request,
    title: str = Form(...),
    sport_type: SportType = Form(...),
    visibility: str = Form("public"),
    started_at: datetime = Form(...),
    polyline: str | None = Form(None),
    distance_m: float | None = Form(None),
    duration_s: int | None = Form(None),
    elevation_gain_m: float | None = Form(None),
    calories: int | None = Form(None),
    file: UploadFile | None = File(None),
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityResponse:
    rate_limit_stub(request)
    from app.schemas.activity import Visibility
    from decimal import Decimal
    try:
        vis = Visibility(visibility)
    except ValueError:
        vis = Visibility.PUBLIC
    data = ActivityCreate(
        title=title,
        sport_type=sport_type,
        visibility=vis,
        started_at=started_at,
        polyline=polyline,
        distance_m=Decimal(str(distance_m)) if distance_m is not None else None,
        duration_s=duration_s,
        elevation_gain_m=Decimal(str(elevation_gain_m)) if elevation_gain_m is not None else None,
        calories=calories,
    )
    service = ActivityService(db)
    if file and file.filename:
        ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        if ext not in settings.allowed_upload_extensions:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .gpx and .tcx files allowed")
        content = await file.read()
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")
        queue = get_queue()
        if queue:
            # Create activity with status=processing; save file and enqueue job
            activity_resp = await service.create(current_user_id, data, create_processing=True)
            upload_dir = Path(settings.upload_dir).resolve()
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_path = upload_dir / f"{activity_resp.id}.{ext}"
            file_path.write_bytes(content)
            await service.repo.update_raw_file_path(UUID(str(activity_resp.id)), str(file_path))
            from app.jobs.tasks import process_activity_job
            queue.enqueue(process_activity_job, str(activity_resp.id))
            return activity_resp
        # No Redis: parse inline (legacy)
        try:
            track_points_from_file = parse_gpx_tcx_to_track_points(content, file.filename or "")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to parse file: {e}")
        return await service.create(current_user_id, data, track_points_from_file=track_points_from_file)
    return await service.create(current_user_id, data)


@router.get("/feed", response_model=list[ActivityListResponse])
async def get_feed(
    request: Request,
    sport_type: SportType | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityListResponse]:
    rate_limit_stub(request)
    if current_user_id is None:
        return []
    from app.services.feed_service import FeedService
    service = FeedService(db)
    return await service.get_feed(
        current_user_id, sport_type=sport_type, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    request: Request,
    activity_id: UUID,
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ActivityResponse:
    rate_limit_stub(request)
    service = ActivityService(db)
    raw = await service.repo.get_by_id(activity_id, load_user=True)
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    from app.services.visibility import can_view_activity
    if not await can_view_activity(db, current_user_id, raw.user_id, raw.visibility):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot view this activity")
    activity = await service.get_by_id(activity_id, current_user_id=current_user_id)
    return activity


@router.get("/{activity_id}/status")
async def get_activity_status(
    request: Request,
    activity_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rate_limit_stub(request)
    from sqlalchemy import select
    from app.models import Activity
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    if activity.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the activity owner can view status")
    return {"status": activity.status.value, "error_message": activity.error_message}


@router.get("/{activity_id}/stream")
async def get_activity_stream(
    request: Request,
    activity_id: UUID,
    max_points: int = Query(500, ge=50, le=2000),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rate_limit_stub(request)
    from sqlalchemy import select
    from app.models import Activity, TrackPoint
    from app.services.gpx_parser import downsample_points
    from app.services.visibility import can_view_activity
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    if not await can_view_activity(db, current_user_id, activity.user_id, activity.visibility):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot view this activity")
    pts_result = await db.execute(
        select(TrackPoint).where(TrackPoint.activity_id == activity_id).order_by(TrackPoint.time)
    )
    pts = list(pts_result.scalars().all())
    if not pts:
        return []
    points_dict = [
        {
            "lat": float(p.lat),
            "lon": float(p.lon),
            "elevation_m": float(p.elevation_m) if p.elevation_m is not None else None,
            "cumulative_distance_m": float(p.cumulative_distance_m) if p.cumulative_distance_m is not None else None,
        }
        for p in pts
    ]
    downsampled = downsample_points(points_dict, max_points=max_points)
    return downsampled


@router.patch("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    request: Request,
    activity_id: UUID,
    data: ActivityUpdate,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityResponse:
    rate_limit_stub(request)
    service = ActivityService(db)
    updated = await service.update(activity_id, current_user_id, data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return updated


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    request: Request,
    activity_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rate_limit_stub(request)
    service = ActivityService(db)
    ok = await service.delete(activity_id, current_user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")


@router.get("/user/{user_id}", response_model=list[ActivityListResponse])
async def list_user_activities(
    request: Request,
    user_id: UUID,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityListResponse]:
    rate_limit_stub(request)
    from app.services.visibility import can_view_activity
    service = ActivityService(db)
    only_ready = current_user_id != user_id
    activities = await service.repo.get_by_user_id(user_id, limit=limit * 2, offset=offset, only_ready=only_ready)
    viewable = []
    for a in activities:
        if await can_view_activity(db, current_user_id, a.user_id, a.visibility):
            viewable.append(a)
        if len(viewable) >= limit:
            break
    out = []
    for a in viewable:
        like_count = await service.repo.count_likes(a.id)
        from sqlalchemy import select, func
        from app.models import Comment, Like
        r = await db.execute(select(func.count(Comment.id)).where(Comment.activity_id == a.id))
        comment_count = r.scalar() or 0
        liked_by_me = False
        if current_user_id:
            r2 = await db.execute(select(Like).where(Like.activity_id == a.id, Like.user_id == current_user_id))
            liked_by_me = r2.scalar_one_or_none() is not None
        from app.schemas import UserPublic, Visibility, ActivityStatus
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
                user=UserPublic.model_validate(a.user) if a.user else None,
                status=ActivityStatus(a.status.value),
            )
        )
    return out
