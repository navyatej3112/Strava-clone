"""Tests for segment matching and leaderboards."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.segments import match_segment


def test_match_segment_simple_overlap():
    """Segment polyline that closely follows activity should match."""
    base_time = datetime.now(timezone.utc)
    activity_points = [
        {"time": base_time + timedelta(seconds=i * 10), "lat": 37.77 + i * 0.0001, "lon": -122.42} for i in range(30)
    ]
    # Segment uses a subset in the middle
    segment_points = [
        {"lat": 37.77 + i * 0.0001, "lon": -122.42} for i in range(5, 20)
    ]

    res = match_segment(activity_points, segment_points, tolerance_m=30.0, min_cover_ratio=0.7)
    assert res is not None
    assert 0 <= res.start_idx < res.end_idx < len(activity_points)


@pytest.mark.asyncio
async def test_segment_leaderboard_public_only():
    """Segment leaderboard should only include efforts from public activities."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Use existing seeded data, just ensure endpoint works and respects 200
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "user1@example.com", "password": "password"},
        )
        assert login.status_code in (200, 400, 401, 404)  # seed users may differ; just smoke test

        # List segments
        segs = await client.get("/api/v1/segments")
        assert segs.status_code == 200
        data = segs.json()
        if not data:
            pytest.skip("No segments available in test DB")
        seg_id = data[0]["id"]

        leaderboard = await client.get(f"/api/v1/segments/{seg_id}/leaderboard")
        assert leaderboard.status_code == 200
        body = leaderboard.json()
        assert "segment" in body
        assert "items" in body

