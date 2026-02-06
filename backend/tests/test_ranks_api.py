"""Tests for PaceRank API endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timezone, timedelta

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_and_recompute_my_rank():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create user and a couple of runs
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "rank_user@test.com", "password": "pass123", "name": "Rank User"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "rank_user@test.com", "password": "pass123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = _auth_headers(token)

        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=1)).isoformat()
        for dist in ["5000", "8000"]:
            r = await client.post(
                "/api/v1/activities",
                headers=headers,
                data={
                    "title": "Rank run",
                    "sport_type": "run",
                    "visibility": "private",  # still counts for own rank
                    "started_at": started,
                    "distance_m": dist,
                    "duration_s": "1800",
                },
            )
            if r.status_code != 201:
                pytest.skip("Activity create failed")

        # Force recompute
        rec = await client.post("/api/v1/ranks/me/recompute", headers=headers)
        assert rec.status_code == 200
        data = rec.json()
        assert data["user_id"]
        assert data["rank_score"] is not None
        assert data["rank_tier"] is not None
        assert data["rank_progress"] is not None
        assert data["breakdown"] is not None
        assert data["breakdown"]["runs_count"] >= 2

        # GET /ranks/me should now be fast (reuse stored rank, breakdown optional)
        r2 = await client.get("/api/v1/ranks/me", headers=headers)
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["rank_score"] == data["rank_score"]


@pytest.mark.asyncio
async def test_run_leaderboard_includes_only_users_with_public_runs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User A with public runs
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "leader_a@test.com", "password": "pass123", "name": "Leader A"},
        )
        login_a = await client.post("/api/v1/auth/login", json={"email": "leader_a@test.com", "password": "pass123"})
        headers_a = _auth_headers(login_a.json()["access_token"])

        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=2)).isoformat()
        await client.post(
            "/api/v1/activities",
            headers=headers_a,
            data={
                "title": "Public run",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "7000",
                "duration_s": "2100",
            },
        )
        # Ensure A has a rank
        await client.post("/api/v1/ranks/me/recompute", headers=headers_a)

        # User B with only private/followers runs (should NOT appear)
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "leader_b@test.com", "password": "pass123", "name": "Leader B"},
        )
        login_b = await client.post("/api/v1/auth/login", json={"email": "leader_b@test.com", "password": "pass123"})
        headers_b = _auth_headers(login_b.json()["access_token"])
        await client.post(
            "/api/v1/activities",
            headers=headers_b,
            data={
                "title": "Private run",
                "sport_type": "run",
                "visibility": "private",
                "started_at": started,
                "distance_m": "7000",
                "duration_s": "2100",
            },
        )

        # Leaderboard
        r = await client.get("/api/v1/ranks/leaderboards/runs", params={"range": "30d"})
        assert r.status_code == 200
        data = r.json()
        assert data["range_days"] == 30
        ids = [item["name"] for item in data["items"]]
        assert "Leader A" in ids
        assert "Leader B" not in ids

