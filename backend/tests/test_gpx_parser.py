"""Tests for GPX/polyline parsing and stats."""
from decimal import Decimal
from datetime import datetime, timezone

from app.services import gpx_parser


def test_compute_stats_empty():
    result = gpx_parser.compute_stats_from_points([])
    assert result["distance_m"] is None
    assert result["duration_s"] is None
    assert result["elevation_gain_m"] is None


def test_compute_stats_single_point():
    t = datetime.now(timezone.utc)
    points = [{"time": t, "lat": 0, "lon": 0, "elevation": 0, "cumulative_distance_m": Decimal(0)}]
    result = gpx_parser.compute_stats_from_points(points)
    assert result["distance_m"] == Decimal(0)
    assert result["duration_s"] is None
    assert result["elevation_gain_m"] == Decimal(0)


def test_encode_polyline_from_points():
    points = [
        {"lat": 37.77, "lon": -122.42, "time": None, "elevation": 0},
        {"lat": 37.78, "lon": -122.43, "time": None, "elevation": 10},
    ]
    encoded = gpx_parser.encode_polyline_from_points(points)
    assert isinstance(encoded, str)
    assert len(encoded) > 0


def test_downsample_points_returns_all_when_under_max():
    points = [{"lat": 37.77 + i * 0.001, "lon": -122.42} for i in range(100)]
    out = gpx_parser.downsample_points(points, max_points=500)
    assert len(out) == 100
    assert out[0]["lat"] == points[0]["lat"]
    assert out[-1]["lat"] == points[-1]["lat"]


def test_downsample_points_reduces_to_max():
    points = [{"lat": 37.77 + i * 0.001, "lon": -122.42} for i in range(1000)]
    out = gpx_parser.downsample_points(points, max_points=100)
    assert len(out) == 100
    assert out[0]["lat"] == points[0]["lat"]
    assert out[-1]["lat"] == points[-1]["lat"]


def test_downsample_points_preserves_first_and_last():
    points = [{"lat": float(i), "lon": float(i)} for i in range(200)]
    out = gpx_parser.downsample_points(points, max_points=10)
    assert out[0] == points[0]
    assert out[-1] == points[-1]
