"""Tests for PaceRank scoring and tier mapping."""
from datetime import datetime, timezone, timedelta

from app.models.activity import ActivitySportType, ActivityStatus
from app.services.rank_service import compute_run_score_30d, score_to_tier, TIERS


class DummyActivity:
    def __init__(
        self,
        distance_m: float,
        duration_s: int,
        elevation_gain_m: float = 0.0,
        calories: int = 0,
        days_ago: int = 0,
    ):
        self.sport_type = ActivitySportType.RUN
        self.status = ActivityStatus.READY
        self.distance_m = distance_m
        self.duration_s = duration_s
        self.elevation_gain_m = elevation_gain_m
        self.calories = calories
        self.started_at = datetime.now(timezone.utc) - timedelta(days=days_ago)


def test_compute_run_score_and_breakdown_basic():
    """Scoring should increase with distance and speed, and ignore tiny runs."""
    # One solid 10 km run and one too-short 500 m jog (ignored)
    activities = [
        DummyActivity(distance_m=10000, duration_s=50 * 60, elevation_gain_m=200, calories=700, days_ago=1),
        DummyActivity(distance_m=500, duration_s=200, elevation_gain_m=0, calories=50, days_ago=2),
    ]
    score, breakdown = compute_run_score_30d(activities)
    assert breakdown.runs_count == 1
    assert breakdown.total_distance_m == 10000
    assert breakdown.total_time_s == 50 * 60
    assert score > 0


def test_score_to_tier_thresholds():
    """Score-to-tier mapping respects configured thresholds."""
    # Pick midpoints of each band
    bronze_mid = 20
    silver_mid = 60
    gold_mid = 100
    platinum_mid = 160
    diamond_mid = 220
    world_class = 300

    t_bronze, next_bronze, prog_b = score_to_tier(bronze_mid)
    assert t_bronze.id == "bronze"
    assert next_bronze and next_bronze.id == "silver"
    assert 0.0 <= prog_b <= 1.0

    t_silver, _, _ = score_to_tier(silver_mid)
    assert t_silver.id == "silver"

    t_gold, _, _ = score_to_tier(gold_mid)
    assert t_gold.id == "gold"

    t_plat, _, _ = score_to_tier(platinum_mid)
    assert t_plat.id == "platinum"

    t_dia, _, _ = score_to_tier(diamond_mid)
    assert t_dia.id == "diamond"

    t_wc, next_wc, prog_wc = score_to_tier(world_class)
    assert t_wc.id == "world_class"
    assert next_wc is None
    assert prog_wc == 1.0

