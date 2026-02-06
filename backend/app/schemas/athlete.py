"""Athlete stats response models."""
from pydantic import BaseModel, Field


class AthleteSummaryTotals(BaseModel):
    activities: int = 0
    distance_m: float = 0
    moving_time_s: int = 0
    elevation_gain_m: float = 0
    calories: int = 0


class AthleteSummaryBySport(BaseModel):
    sport_type: str
    activities: int = 0
    distance_m: float = 0
    moving_time_s: int = 0
    elevation_gain_m: float = 0


class AthleteSummaryResponse(BaseModel):
    range: str
    from_: str = Field(alias="from")  # ISO date/datetime
    to: str
    totals: AthleteSummaryTotals
    by_sport: list[AthleteSummaryBySport]

    model_config = {"populate_by_name": True}


class AthleteWeekResponse(BaseModel):
    week_start: str  # YYYY-MM-DD Monday
    distance_m: float = 0
    activities: int = 0
