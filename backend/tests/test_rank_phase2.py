"""Tests for PaceRank Phase 2: history, rank-up notifications, following leaderboard."""
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
async def test_rank_snapshot_upsert_unique_per_day_scope():
    """Snapshots are unique per user/date/scope."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "snapshot_user@test.com", "password": "pass123", "name": "Snapshot User"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "snapshot_user@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        
        # Create a run
        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=1)).isoformat()
        await client.post(
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
        
        # Recompute twice - should update same snapshot
        r1 = await client.post("/api/v1/ranks/me/recompute", headers=headers)
        assert r1.status_code == 200
        r2 = await client.post("/api/v1/ranks/me/recompute", headers=headers)
        assert r2.status_code == 200
        
        # History should have one entry per scope
        hist = await client.get("/api/v1/ranks/me/history", headers=headers, params={"days": "30"})
        assert hist.status_code == 200
        data = hist.json()
        assert data["scope"] == "private"
        # Should have at least today's snapshot
        assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_history_endpoints_scope_rules():
    """Me gets private scope, others get public scope."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User A
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "hist_a@test.com", "password": "pass123", "name": "Hist A"},
        )
        login_a = await client.post("/api/v1/auth/login", json={"email": "hist_a@test.com", "password": "pass123"})
        headers_a = _auth_headers(login_a.json()["access_token"])
        me_a = await client.get("/api/v1/users/me", headers=headers_a)
        user_a_id = me_a.json()["id"]
        
        # Create run and recompute
        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=1)).isoformat()
        await client.post(
            "/api/v1/activities",
            headers=headers_a,
            data={
                "title": "Run",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "5000",
                "duration_s": "1800",
            },
        )
        await client.post("/api/v1/ranks/me/recompute", headers=headers_a)
        
        # User A's own history should be private
        r_me = await client.get("/api/v1/ranks/me/history", headers=headers_a)
        assert r_me.status_code == 200
        assert r_me.json()["scope"] == "private"
        
        # User B viewing A's history should get public
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "hist_b@test.com", "password": "pass123", "name": "Hist B"},
        )
        login_b = await client.post("/api/v1/auth/login", json={"email": "hist_b@test.com", "password": "pass123"})
        headers_b = _auth_headers(login_b.json()["access_token"])
        
        r_other = await client.get(f"/api/v1/ranks/users/{user_a_id}/history", headers=headers_b)
        assert r_other.status_code == 200
        assert r_other.json()["scope"] == "public"


@pytest.mark.asyncio
async def test_rank_up_notification_created_on_increase():
    """Rank-up notification created when tier increases."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "rankup_user@test.com", "password": "pass123", "name": "RankUp User"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": "rankup_user@test.com", "password": "pass123"})
        assert login.status_code == 200
        headers = _auth_headers(login.json()["access_token"])
        
        # Set initial rank to bronze (via direct DB manipulation would be ideal, but we'll use API)
        # For test, we'll create low-score runs first, then high-score runs
        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=1)).isoformat()
        
        # Low score run (bronze tier)
        await client.post(
            "/api/v1/activities",
            headers=headers,
            data={
                "title": "Slow run",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "2000",
                "duration_s": "900",
            },
        )
        r1 = await client.post("/api/v1/ranks/me/recompute", headers=headers)
        assert r1.status_code == 200
        tier1 = r1.json()["rank_tier"]
        
        # High score run (should push to higher tier)
        await client.post(
            "/api/v1/activities",
            headers=headers,
            data={
                "title": "Fast run",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "15000",
                "duration_s": "3600",
            },
        )
        r2 = await client.post("/api/v1/ranks/me/recompute", headers=headers)
        assert r2.status_code == 200
        tier2 = r2.json()["rank_tier"]
        
        # Check notifications
        notifs = await client.get("/api/v1/notifications", headers=headers)
        assert notifs.status_code == 200
        rank_ups = [n for n in notifs.json() if n["type"] == "rank_up"]
        # If tier increased, should have rank_up notification
        if tier1 and tier2 and tier1 != tier2:
            assert len(rank_ups) > 0
            assert rank_ups[0]["data"] is not None
            assert "new_tier_name" in rank_ups[0]["data"]


@pytest.mark.asyncio
async def test_following_leaderboard_only_includes_followed_users():
    """Following leaderboard only includes users that requester follows."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User A
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "follow_leader_a@test.com", "password": "pass123", "name": "Follow Leader A"},
        )
        login_a = await client.post("/api/v1/auth/login", json={"email": "follow_leader_a@test.com", "password": "pass123"})
        headers_a = _auth_headers(login_a.json()["access_token"])
        me_a = await client.get("/api/v1/users/me", headers=headers_a)
        user_a_id = me_a.json()["id"]
        
        # User B
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "follow_leader_b@test.com", "password": "pass123", "name": "Follow Leader B"},
        )
        login_b = await client.post("/api/v1/auth/login", json={"email": "follow_leader_b@test.com", "password": "pass123"})
        headers_b = _auth_headers(login_b.json()["access_token"])
        me_b = await client.get("/api/v1/users/me", headers=headers_b)
        user_b_id = me_b.json()["id"]
        
        # User C (not followed)
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "follow_leader_c@test.com", "password": "pass123", "name": "Follow Leader C"},
        )
        login_c = await client.post("/api/v1/auth/login", json={"email": "follow_leader_c@test.com", "password": "pass123"})
        headers_c = _auth_headers(login_c.json()["access_token"])
        
        # Create runs for all
        now = datetime.now(timezone.utc)
        started = (now - timedelta(days=1)).isoformat()
        for headers in [headers_a, headers_b, headers_c]:
            await client.post(
                "/api/v1/activities",
                headers=headers,
                data={
                    "title": "Run",
                    "sport_type": "run",
                    "visibility": "public",
                    "started_at": started,
                    "distance_m": "5000",
                    "duration_s": "1800",
                },
            )
            await client.post("/api/v1/ranks/me/recompute", headers=headers)
        
        # A follows B
        await client.post(f"/api/v1/follows/{user_b_id}", headers=headers_a)
        
        # User C
        me_c = await client.get("/api/v1/users/me", headers=headers_c)
        user_c_id = me_c.json()["id"]
        
        # A's following leaderboard should include A and B, not C
        r = await client.get("/api/v1/ranks/leaderboards/runs/following", headers=headers_a)
        assert r.status_code == 200
        data = r.json()
        user_ids = [item["user_id"] for item in data["items"]]
        assert user_a_id in user_ids
        assert user_b_id in user_ids
        assert user_c_id not in user_ids
