"""Activity schemas."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from .segment import SegmentEffortResponse
class SportType(str, Enum):
    RUN = "run"
    RIDE = "ride"
    WALK = "walk"


class Visibility(str, Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"


class ActivityStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ActivityBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    sport_type: SportType
    visibility: Visibility = Visibility.PUBLIC
    started_at: datetime


class ActivityCreate(ActivityBase):
    polyline: str | None = Field(None, description="Encoded polyline; if provided, stats can be computed")
    distance_m: Decimal | None = None
    duration_s: int | None = None
    elevation_gain_m: Decimal | None = None
    calories: int | None = None


class ActivityUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    visibility: Visibility | None = None


class SplitResponse(BaseModel):
    index: int
    distance_m: Decimal
    duration_s: int
    pace_per_km_s: float | None = None  # for run/walk
    speed_kmh: float | None = None  # for ride


class ElevationPoint(BaseModel):
    distance_m: Decimal
    elevation_m: Decimal
    time_iso: str | None = None


class ActivityResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    sport_type: SportType
    visibility: Visibility
    started_at: datetime
    distance_m: Decimal | None
    duration_s: int | None
    elevation_gain_m: Decimal | None
    calories: int | None
    polyline: str | None
    created_at: datetime
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    user: "UserPublic | None" = None
    splits: list[SplitResponse] | None = None
    elevation_profile: list[ElevationPoint] | None = None
    status: ActivityStatus = ActivityStatus.READY
    error_message: str | None = None
    rank_eligible: bool = True
    rank_excluded_reason: str | None = None
    max_speed_kmh: float | None = None
    segments: list[SegmentEffortResponse] | None = None

    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    sport_type: SportType
    visibility: Visibility
    started_at: datetime
    distance_m: Decimal | None
    duration_s: int | None
    elevation_gain_m: Decimal | None
    calories: int | None
    polyline: str | None
    created_at: datetime
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    user: "UserPublic | None" = None
    status: ActivityStatus = ActivityStatus.READY

    model_config = {"from_attributes": True}


# Resolve forward ref
from app.schemas.user import UserPublic  # noqa: E402

ActivityResponse.model_rebuild()
ActivityListResponse.model_rebuild()
