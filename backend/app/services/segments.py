"""Segment matching and effort computation."""
from __future__ import annotations

from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
from typing import Iterable

import polyline as pl


def decode_polyline_to_points(encoded: str) -> list[dict]:
    """Decode an encoded polyline into list of {lat, lon} dicts."""
    coords = pl.decode(encoded)
    return [{"lat": lat, "lon": lon} for lat, lon in coords]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters."""
    R = 6371000.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlam / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def downsample_points(points: list[dict], max_points: int = 200) -> list[dict]:
    """Simple downsampling by picking every N-th point."""
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    return [p for idx, p in enumerate(points) if idx % step == 0]


@dataclass
class MatchResult:
    start_idx: int
    end_idx: int


def match_segment(
    activity_points: list[dict],
    segment_points: list[dict],
    tolerance_m: float = 40.0,
    min_cover_ratio: float = 0.8,
) -> MatchResult | None:
    """Heuristic matching of segment polyline against activity track.

    For each segment point, find nearest activity point within tolerance.
    Require strictly increasing activity indices and that at least `min_cover_ratio`
    of segment points find a match.
    """
    if not activity_points or not segment_points:
        return None

    matched_indices: list[int] = []

    last_idx = -1
    for sp in segment_points:
        best_idx = None
        best_dist = None
        for i in range(last_idx + 1, len(activity_points)):
            ap = activity_points[i]
            dist = _haversine_m(float(sp["lat"]), float(sp["lon"]), float(ap["lat"]), float(ap["lon"]))
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx is not None and best_dist is not None and best_dist <= tolerance_m:
            matched_indices.append(best_idx)
            last_idx = best_idx

    if not matched_indices:
        return None

    cover_ratio = len(matched_indices) / float(len(segment_points))
    if cover_ratio < min_cover_ratio:
        return None

    return MatchResult(start_idx=min(matched_indices), end_idx=max(matched_indices))


def compute_effort_stats(points: list[dict], start_idx: int, end_idx: int) -> tuple[int, float]:
    """Compute effort_time_s and effort_distance_m over [start_idx, end_idx]."""
    if end_idx <= start_idx or end_idx >= len(points):
        return 0, 0.0
    start = points[start_idx]
    end = points[end_idx]
    t1, t2 = start.get("time"), end.get("time")
    if not t1 or not t2:
        return 0, 0.0
    duration_s = int((t2 - t1).total_seconds())
    if duration_s <= 0:
        return 0, 0.0

    distance = 0.0
    prev = points[start_idx]
    for i in range(start_idx + 1, end_idx + 1):
        cur = points[i]
        distance += _haversine_m(float(prev["lat"]), float(prev["lon"]), float(cur["lat"]), float(cur["lon"]))
        prev = cur
    return duration_s, distance


def trackpoints_to_points(trackpoints: Iterable["TrackPoint"]) -> list[dict]:  # type: ignore[name-defined]
    """Convert TrackPoint ORM objects into list[{time, lat, lon}]."""
    pts: list[dict] = []
    for tp in trackpoints:
        if not tp.time:
            continue
        pts.append(
            {
                "time": tp.time,
                "lat": float(tp.lat),
                "lon": float(tp.lon),
            }
        )
    return pts


