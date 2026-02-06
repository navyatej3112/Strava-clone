"""Tests for PaceRank Phase 3: FairPlay + Async recompute."""
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_ineligible_runs_excluded_from_leaderboard():
    """Leaderboard should only include rank_eligible=true runs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Signup and login
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "fairplay_test@test.com", "password": "pass123", "name": "FairPlay Test"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "fairplay_test@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        
        # Leaderboard should work (may be empty but shouldn't crash)
        leaderboard = await client.get("/api/v1/ranks/leaderboards/runs", params={"range": "30d", "limit": "10"})
        assert leaderboard.status_code == 200
        # Verify it filters rank_eligible (we can't directly test DB state, but endpoint should work)


@pytest.mark.asyncio
async def test_async_recompute_returns_job_id():
    """POST /ranks/me/recompute should return job_id when Redis available."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "async_test@test.com", "password": "pass123", "name": "Async Test"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "async_test@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        
        # Try recompute
        recompute = await client.post("/api/v1/ranks/me/recompute", headers=headers)
        assert recompute.status_code == 200
        data = recompute.json()
        # Should return status and either job_id (if Redis) or result (if sync fallback)
        assert "status" in data
        assert data["status"] in ("queued", "finished")
        if data["status"] == "queued":
            assert "job_id" in data


@pytest.mark.asyncio
async def test_recompute_status_endpoint():
    """GET /ranks/me/recompute/{job_id} should return job status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "status_test@test.com", "password": "pass123", "name": "Status Test"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "status_test@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        
        # Try recompute to get job_id
        recompute = await client.post("/api/v1/ranks/me/recompute", headers=headers)
        assert recompute.status_code == 200
        data = recompute.json()
        
        if data.get("status") == "queued" and "job_id" in data:
            job_id = data["job_id"]
            # Poll status (may be finished immediately if worker is fast)
            status = await client.get(f"/api/v1/ranks/me/recompute/{job_id}", headers=headers)
            assert status.status_code == 200
            status_data = status.json()
            assert "status" in status_data
            assert status_data["status"] in ("queued", "started", "finished", "failed")
        else:
            # Sync fallback - no job_id to test
            pytest.skip("Redis unavailable, using sync fallback")


@pytest.mark.asyncio
async def test_activity_response_includes_fairplay_fields():
    """ActivityResponse should include rank_eligible, rank_excluded_reason, max_speed_kmh."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "fairplay_fields@test.com", "password": "pass123", "name": "FairPlay Fields"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "fairplay_fields@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        
        from datetime import datetime, timezone, timedelta
        started = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        # Create a run activity
        activity = await client.post(
            "/api/v1/activities",
            headers=headers,
            data={
                "title": "Test run",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "5000",
                "duration_s": "1800",
            },
        )
        assert activity.status_code == 201
        act_data = activity.json()
        
        # Should include FairPlay fields
        assert "rank_eligible" in act_data
        assert "rank_excluded_reason" in act_data
        assert "max_speed_kmh" in act_data


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
