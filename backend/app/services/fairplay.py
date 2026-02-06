"""FairPlay: detect suspicious runs and exclude from PaceRank."""
from typing import Optional


def compute_max_speed_kmh(points: list[dict]) -> Optional[float]:
    """Compute max speed from track points (per-segment speeds)."""
    if len(points) < 2:
        return None
    
    max_speed = 0.0
    for i in range(1, len(points)):
        p1 = points[i - 1]
        p2 = points[i]
        
        if "time" not in p1 or "time" not in p2:
            continue
        if "lat" not in p1 or "lon" not in p1 or "lat" not in p2 or "lon" not in p2:
            continue
        
        dt = (p2["time"] - p1["time"]).total_seconds()
        if dt <= 0:
            continue
        
        # Haversine distance
        from math import radians, sin, cos, sqrt, atan2
        
        lat1, lon1 = radians(float(p1["lat"])), radians(float(p1["lon"]))
        lat2, lon2 = radians(float(p2["lat"])), radians(float(p2["lon"]))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance_m = 6371000 * c  # Earth radius in meters
        
        speed_ms = distance_m / dt
        speed_kmh = speed_ms * 3.6
        
        # Clamp extremes (ignore GPS glitches)
        if 0 < speed_kmh < 100:
            max_speed = max(max_speed, speed_kmh)
    
    return max_speed if max_speed > 0 else None


def is_suspicious_run(
    distance_m: Optional[float],
    duration_s: Optional[int],
    max_speed_kmh: Optional[float],
) -> tuple[bool, Optional[str]]:
    """
    Check if a RUN activity is suspicious (likely vehicle or unrealistic).
    Returns (is_suspicious, reason).
    """
    if distance_m is None or duration_s is None:
        return False, None
    
    distance_m_val = float(distance_m)
    duration_s_val = int(duration_s)
    
    # Too short: already filtered in score computation, but mark explicitly
    if duration_s_val < 300 or distance_m_val < 1000:
        return True, "too_short"
    
    # Compute avg speed
    if duration_s_val > 0:
        hours = duration_s_val / 3600.0
        avg_speed_kmh = (distance_m_val / 1000.0) / hours
    else:
        return True, "too_short"
    
    # Max speed too high (likely vehicle)
    if max_speed_kmh is not None and max_speed_kmh >= 28.0:
        return True, "max_speed_too_high"
    
    # Avg speed too high (sustained unrealistic pace)
    if avg_speed_kmh >= 22.0:
        return True, "avg_speed_too_high"
    
    # Distance/time unrealistic (very long distance in very short time)
    if distance_m_val > 60000 and duration_s_val < 7200:  # >60km in <2h
        return True, "distance_time_unrealistic"
    
    return False, None
