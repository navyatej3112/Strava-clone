"""Schemas for PaceRank (runner ranking)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RankBreakdown(BaseModel):
    runs_count: int
    active_days: int
    total_distance_m: float
    total_time_s: int
    avg_speed_kmh: float
    total_elevation_gain_m: float
    total_calories: int
    score: float


class RankMeResponse(BaseModel):
    user_id: str
    rank_tier: Optional[str]
    rank_tier_name: Optional[str]
    rank_score: Optional[float]
    rank_range_days: int
    rank_last_computed_at: Optional[datetime]
    rank_progress: Optional[float]
    rank_next_tier: Optional[str]
    breakdown: Optional[RankBreakdown]


class TierInfo(BaseModel):
    id: str
    name: str
    min_score: float
    max_score: Optional[float]  # None for top tier


class RunLeaderboardItem(BaseModel):
    user_id: str
    name: str
    rank_tier: Optional[str]
    rank_tier_name: Optional[str]
    rank_score: Optional[float]
    runs_count_public: int
    total_distance_public_m: float


class RunLeaderboardResponse(BaseModel):
    range_days: int
    items: list[RunLeaderboardItem]


class RankSnapshotItem(BaseModel):
    date: str  # YYYY-MM-DD
    tier_id: str
    tier_name: str
    score: float


class RankHistoryResponse(BaseModel):
    user_id: str
    scope: str  # "private" or "public"
    days: int
    items: list[RankSnapshotItem]

