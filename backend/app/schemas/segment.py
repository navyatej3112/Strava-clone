"""Schemas for segments and segment efforts."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SegmentCreate(BaseModel):
    name: str
    description: str | None = None
    polyline: str
    is_public: bool = True


class SegmentResponse(BaseModel):
    id: UUID
    owner_user_id: UUID
    name: str
    description: str | None = None
    polyline: str
    distance_m: float
    is_public: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SegmentEffortResponse(BaseModel):
    id: UUID
    segment_id: UUID
    activity_id: UUID
    user_id: UUID
    segment_name: str | None = None
    effort_time_s: int
    effort_distance_m: float
    avg_speed_kmh: float
    started_at: datetime
    visibility: str
    is_pr: bool | None = None  # filled on read
    is_kom: bool | None = None  # filled on read


class SegmentLeaderboardItem(BaseModel):
    user_id: UUID
    name: str | None
    activity_id: UUID
    effort_time_s: int
    effort_distance_m: float
    avg_speed_kmh: float
    started_at: datetime
    is_kom: bool | None = None


class SegmentLeaderboardResponse(BaseModel):
    segment: SegmentResponse
    items: list[SegmentLeaderboardItem]
    kom: dict | None = None


