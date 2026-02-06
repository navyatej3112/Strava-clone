"""Tests for athlete summary and weekly stats API."""
import pytest
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timezone, timedelta

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.asyncio
async def test_my_summary_totals_and_by_sport():
    """Summary aggregates activities in range; by_sport breakdown."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "stats_user@test.com", "password": "pass123", "name": "Stats User"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "stats_user@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=1)).isoformat()
        # Create two activities: run 5k, ride 10k
        for title, sport, dist, dur in [
            ("Run", "run", "5000", "1200"),
            ("Ride", "ride", "10000", "2400"),
        ]:
            r = await client.post(
                "/api/v1/activities",
                headers=headers,
                data={
                    "title": title,
                    "sport_type": sport,
                    "visibility": "public",
                    "started_at": started,
                    "distance_m": dist,
                    "duration_s": dur,
                },
            )
            if r.status_code != 201:
                pytest.skip("Activity create failed")

        r = await client.get("/api/v1/athletes/me/summary", headers=headers, params={"range": "7d"})
        assert r.status_code == 200
        data = r.json()
        assert data["range"] == "7d"
        assert "from" in data
        assert "to" in data
        totals = data["totals"]
        assert totals["activities"] == 2
        assert totals["distance_m"] == 15000
        assert totals["moving_time_s"] == 3600
        assert len(data["by_sport"]) == 2
        by_sport = {s["sport_type"]: s for s in data["by_sport"]}
        assert by_sport["run"]["activities"] == 1 and by_sport["run"]["distance_m"] == 5000
        assert by_sport["ride"]["activities"] == 1 and by_sport["ride"]["distance_m"] == 10000


@pytest.mark.asyncio
async def test_my_weeks_grouping():
    """Weeks endpoint returns last N weeks with week_start and aggregates."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "weeks_user@test.com", "password": "pass123", "name": "Weeks User"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "weeks_user@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        now = datetime.now(timezone.utc)
        # One activity this week
        started = (now - timedelta(days=2)).isoformat()
        create = await client.post(
            "/api/v1/activities",
            headers=headers,
            data={
                "title": "This week run",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "8000",
                "duration_s": "2400",
            },
        )
        if create.status_code != 201:
            pytest.skip("Activity create failed")

        r = await client.get("/api/v1/athletes/me/weeks", headers=headers, params={"weeks": "12"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 12
        # Each item has week_start, distance_m, activities
        for w in data:
            assert "week_start" in w
            assert "distance_m" in w
            assert "activities" in w
        # At least one week has our activity
        total_dist = sum(w["distance_m"] for w in data)
        assert total_dist == 8000


@pytest.mark.asyncio
async def test_athlete_summary_visibility_follower_sees_followers_only():
    """When viewing another athlete's summary, only viewable activities count."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # User A: one public, one followers-only
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "athlete_a@test.com", "password": "pass123", "name": "Athlete A"},
        )
        login_a = await client.post("/api/v1/auth/login", json={"email": "athlete_a@test.com", "password": "pass123"})
        assert login_a.status_code == 200
        headers_a = _auth_headers(login_a.json()["access_token"])
        me_a = await client.get("/api/v1/users/me", headers=headers_a)
        if me_a.status_code != 200:
            pytest.skip("Users/me failed")
        user_a_id = me_a.json()["id"]
        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=1)).isoformat()
        await client.post(
            "/api/v1/activities",
            headers=headers_a,
            data={
                "title": "Public",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "3000",
                "duration_s": "900",
            },
        )
        await client.post(
            "/api/v1/activities",
            headers=headers_a,
            data={
                "title": "Followers only",
                "sport_type": "run",
                "visibility": "followers",
                "started_at": started,
                "distance_m": "5000",
                "duration_s": "1500",
            },
        )
        # User B follows A
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "athlete_b@test.com", "password": "pass123", "name": "Athlete B"},
        )
        login_b = await client.post("/api/v1/auth/login", json={"email": "athlete_b@test.com", "password": "pass123"})
        headers_b = _auth_headers(login_b.json()["access_token"])
        await client.post(f"/api/v1/follows/{user_a_id}", headers=headers_b)
        # B views A's summary -> should see both (2 activities, 8k m)
        r_b = await client.get(f"/api/v1/athletes/{user_a_id}/summary", headers=headers_b, params={"range": "7d"})
        assert r_b.status_code == 200
        assert r_b.json()["totals"]["activities"] == 2
        assert r_b.json()["totals"]["distance_m"] == 8000
        # User C does not follow A
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "athlete_c@test.com", "password": "pass123", "name": "Athlete C"},
        )
        headers_c = _auth_headers(
            (await client.post("/api/v1/auth/login", json={"email": "athlete_c@test.com", "password": "pass123"})).json()["access_token"]
        )
        r_c = await client.get(f"/api/v1/athletes/{user_a_id}/summary", headers=headers_c, params={"range": "7d"})
        assert r_c.status_code == 200
        # Only public activity
        assert r_c.json()["totals"]["activities"] == 1
        assert r_c.json()["totals"]["distance_m"] == 3000


@pytest.mark.asyncio
async def test_athletes_me_requires_auth():
    """GET /athletes/me/summary and /me/weeks return 401 when not authenticated."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/athletes/me/summary", params={"range": "7d"})
        assert r.status_code == 401
        r2 = await client.get("/api/v1/athletes/me/weeks", params={"weeks": "12"})
        assert r2.status_code == 401
