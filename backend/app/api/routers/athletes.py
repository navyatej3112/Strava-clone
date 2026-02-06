"""Athlete stats: summary and weekly chart."""
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user_optional
from app.repositories.activity_repository import ActivityRepository
from app.services.visibility import can_view_activity
from app.schemas.athlete import (
    AthleteSummaryResponse,
    AthleteSummaryTotals,
    AthleteSummaryBySport,
    AthleteWeekResponse,
)

router = APIRouter(prefix="/athletes", tags=["athletes"])


def _range_bounds(range_key: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if range_key == "7d":
        date_from = now - timedelta(days=7)
        return date_from, now
    if range_key == "30d":
        date_from = now - timedelta(days=30)
        return date_from, now
    if range_key == "ytd":
        date_from = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return date_from, now
    raise ValueError("range must be 7d, 30d, or ytd")




@router.get("/me/summary", response_model=AthleteSummaryResponse)
async def get_my_summary(
    range: str = Query("30d", alias="range"),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> AthleteSummaryResponse:
    if not current_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        date_from, date_to = _range_bounds(range)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="range must be 7d, 30d, or ytd")
    repo = ActivityRepository(db)
    activities = await repo.get_by_user_id_in_date_range(current_user_id, date_from, date_to)
    return _build_summary(activities, range, date_from, date_to)


@router.get("/{athlete_id}/summary", response_model=AthleteSummaryResponse)
async def get_athlete_summary(
    athlete_id: UUID,
    range: str = Query("30d", alias="range"),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> AthleteSummaryResponse:
    try:
        date_from, date_to = _range_bounds(range)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="range must be 7d, 30d, or ytd")
    repo = ActivityRepository(db)
    activities = await repo.get_by_user_id_in_date_range(athlete_id, date_from, date_to)
    viewable = []
    for a in activities:
        if await can_view_activity(db, current_user_id, a.user_id, a.visibility):
            viewable.append(a)
    return _build_summary(viewable, range, date_from, date_to)


def _build_summary(activities: list, range_key: str, date_from: datetime, date_to: datetime) -> AthleteSummaryResponse:
    totals = AthleteSummaryTotals(activities=len(activities))
    by_sport_map: dict[str, dict] = defaultdict(lambda: {"activities": 0, "distance_m": 0, "moving_time_s": 0, "elevation_gain_m": 0})
    for a in activities:
        dist = float(a.distance_m) if a.distance_m is not None else 0
        dur = int(a.duration_s) if a.duration_s is not None else 0
        elev = float(a.elevation_gain_m) if a.elevation_gain_m is not None else 0
        cal = int(a.calories) if a.calories is not None else 0
        totals.distance_m += dist
        totals.moving_time_s += dur
        totals.elevation_gain_m += elev
        totals.calories += cal
        st = a.sport_type.value
        by_sport_map[st]["activities"] += 1
        by_sport_map[st]["distance_m"] += dist
        by_sport_map[st]["moving_time_s"] += dur
        by_sport_map[st]["elevation_gain_m"] += elev
    by_sport = [
        AthleteSummaryBySport(sport_type=k, activities=v["activities"], distance_m=v["distance_m"], moving_time_s=v["moving_time_s"], elevation_gain_m=v["elevation_gain_m"])
        for k, v in sorted(by_sport_map.items())
    ]
    return AthleteSummaryResponse(
        range=range_key,
        from_=date_from.isoformat(),
        to=date_to.isoformat(),
        totals=totals,
        by_sport=by_sport,
    )


def _week_start(dt: datetime) -> str:
    """Monday 00:00 UTC for the week containing dt."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    d = dt.date()
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()


def _build_weeks(activities: list, date_from: datetime, date_to: datetime, weeks: int) -> list[AthleteWeekResponse]:
    by_week: dict[str, dict] = defaultdict(lambda: {"distance_m": 0, "activities": 0})
    for a in activities:
        ws = _week_start(a.started_at)
        dist = float(a.distance_m) if a.distance_m is not None else 0
        by_week[ws]["distance_m"] += dist
        by_week[ws]["activities"] += 1
    # Last N weeks: from (today - N weeks) Monday to current week Monday
    now = date_to
    end_monday = (now.date() - timedelta(days=now.date().weekday()))
    start_monday = end_monday - timedelta(weeks=weeks - 1)
    result = []
    for i in range(weeks):
        monday = start_monday + timedelta(weeks=i)
        ws = monday.isoformat()
        result.append(AthleteWeekResponse(
            week_start=ws,
            distance_m=by_week.get(ws, {}).get("distance_m", 0) or 0,
            activities=by_week.get(ws, {}).get("activities", 0) or 0,
        ))
    return result


@router.get("/me/weeks", response_model=list[AthleteWeekResponse])
async def get_my_weeks(
    weeks: int = Query(12, ge=1, le=52),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[AthleteWeekResponse]:
    if not current_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    now = datetime.now(timezone.utc)
    date_to = now
    date_from = now - timedelta(weeks=weeks)
    repo = ActivityRepository(db)
    activities = await repo.get_by_user_id_in_date_range(current_user_id, date_from, date_to)
    return _build_weeks(activities, date_from, date_to, weeks)


@router.get("/{athlete_id}/weeks", response_model=list[AthleteWeekResponse])
async def get_athlete_weeks(
    athlete_id: UUID,
    weeks: int = Query(12, ge=1, le=52),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[AthleteWeekResponse]:
    now = datetime.now(timezone.utc)
    date_to = now
    date_from = now - timedelta(weeks=weeks)
    repo = ActivityRepository(db)
    activities = await repo.get_by_user_id_in_date_range(athlete_id, date_from, date_to)
    viewable = []
    for a in activities:
        if await can_view_activity(db, current_user_id, a.user_id, a.visibility):
            viewable.append(a)
    return _build_weeks(viewable, date_from, date_to, weeks)
