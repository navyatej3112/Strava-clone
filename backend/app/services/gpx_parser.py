"""Parse GPX/TCX and compute stats; encode polyline."""
import io
from datetime import datetime, timezone
from decimal import Decimal
from math import radians, sin, cos, sqrt, atan2

import gpxpy
import polyline as pl

# Haversine distance in meters
def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlam = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlam / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def parse_gpx(content: bytes | str) -> list[dict]:
    """Parse GPX file content; return list of {time, lat, lon, elevation, cumulative_distance_m}."""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    gpx = gpxpy.parse(io.StringIO(content))
    points = []
    cumulative = 0.0
    prev = None
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                lat = pt.latitude
                lon = pt.longitude
                ele = pt.elevation or 0.0
                t = pt.time
                if t and t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                if prev:
                    cumulative += _haversine_m(prev["lat"], prev["lon"], lat, lon)
                points.append({
                    "time": t or datetime.now(timezone.utc),
                    "lat": lat,
                    "lon": lon,
                    "elevation": ele,
                    "cumulative_distance_m": Decimal(str(round(cumulative, 2))),
                })
                prev = points[-1]
    return points


def parse_tcx(content: bytes | str) -> list[dict]:
    """Parse TCX file content; return same structure as GPX."""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    # gpxpy can parse some TCX; for full TCX we'd use a TCX library. Fallback: minimal XML parse.
    try:
        gpx = gpxpy.parse(io.StringIO(content))
        return parse_gpx(content)
    except Exception:
        pass
    # Minimal TCX parsing for <Trackpoint>
    import xml.etree.ElementTree as ET
    ns = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    root = ET.fromstring(content)
    points = []
    cumulative = 0.0
    prev = None
    for tp in root.iter("{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}Trackpoint"):
        time_el = tp.find("ns:Time", ns)
        pos = tp.find("ns:Position", ns)
        alt = tp.find("ns:AltitudeMeters", ns)
        if time_el is None or pos is None:
            continue
        lat_el = pos.find("ns:LatitudeDegrees", ns)
        lon_el = pos.find("ns:LongitudeDegrees", ns)
        if lat_el is None or lon_el is None:
            continue
        lat = float(lat_el.text)
        lon = float(lon_el.text)
        ele = float(alt.text) if alt is not None and alt.text else 0.0
        try:
            from datetime import datetime as dt
            t = dt.fromisoformat(time_el.text.replace("Z", "+00:00"))
        except Exception:
            t = datetime.now(timezone.utc)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if prev:
            cumulative += _haversine_m(prev["lat"], prev["lon"], lat, lon)
        points.append({
            "time": t,
            "lat": lat,
            "lon": lon,
            "elevation": ele,
            "cumulative_distance_m": Decimal(str(round(cumulative, 2))),
        })
        prev = points[-1]
    return points


def parse_gpx_tcx_to_track_points(content: bytes, filename: str) -> list[dict]:
    """Dispatch by extension; return list of track point dicts."""
    lower = filename.lower()
    if lower.endswith(".gpx"):
        return parse_gpx(content)
    if lower.endswith(".tcx"):
        return parse_tcx(content)
    raise ValueError("Unsupported file type; use .gpx or .tcx")


def compute_stats_from_points(points: list[dict]) -> dict:
    """Compute distance_m, duration_s, elevation_gain_m from track points."""
    if not points:
        return {"distance_m": None, "duration_s": None, "elevation_gain_m": None}
    distance_m = None
    if points:
        last = points[-1].get("cumulative_distance_m")
        if last is not None:
            distance_m = last
        else:
            dist = 0.0
            for i in range(1, len(points)):
                p1, p2 = points[i - 1], points[i]
                dist += _haversine_m(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
            distance_m = Decimal(str(round(dist, 2)))
    duration_s = None
    if len(points) >= 2:
        start = points[0].get("time")
        end = points[-1].get("time")
        if start and end:
            duration_s = int((end - start).total_seconds())
    elevation_gain_m = None
    if points:
        gain = 0.0
        for i in range(1, len(points)):
            a, b = points[i - 1].get("elevation", 0) or 0, points[i].get("elevation", 0) or 0
            if b > a:
                gain += float(b - a)
        elevation_gain_m = Decimal(str(round(gain, 2)))
    return {"distance_m": distance_m, "duration_s": duration_s, "elevation_gain_m": elevation_gain_m}


def encode_polyline_from_points(points: list[dict]) -> str:
    """Encode list of {lat, lon} to Google-style polyline."""
    coords = [(p["lat"], p["lon"]) for p in points]
    return pl.encode(coords)


def downsample_points(points: list[dict], max_points: int = 500) -> list[dict]:
    """Reduce number of points for map rendering (stride-based). Preserves first and last."""
    if len(points) <= max_points:
        return points
    step = (len(points) - 1) / (max_points - 1)
    indices = [0] + [int(round(i * step)) for i in range(1, max_points - 1)] + [len(points) - 1]
    return [points[i] for i in indices]
