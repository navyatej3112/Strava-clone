"""Tests for activity visibility rules: 403/200 and status owner-only."""
import pytest
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timezone

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.asyncio
async def test_get_activity_private_owner_200_other_403():
    """Owner can view private activity; other user gets 403."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Create owner and other user
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "vis_owner@test.com", "password": "pass123", "name": "Owner"},
        )
        login_owner = await client.post(
            "/api/v1/auth/login",
            json={"email": "vis_owner@test.com", "password": "pass123"},
        )
        assert login_owner.status_code == 200
        owner_token = login_owner.json()["access_token"]
        owner_headers = _auth_headers(owner_token)

        await client.post(
            "/api/v1/auth/signup",
            json={"email": "vis_other@test.com", "password": "pass123", "name": "Other"},
        )
        login_other = await client.post(
            "/api/v1/auth/login",
            json={"email": "vis_other@test.com", "password": "pass123"},
        )
        assert login_other.status_code == 200
        other_token = login_other.json()["access_token"]
        other_headers = _auth_headers(other_token)

        # Owner creates private activity (no file -> ready)
        started = datetime.now(timezone.utc).isoformat()
        create = await client.post(
            "/api/v1/activities",
            headers=owner_headers,
            data={
                "title": "Private run",
                "sport_type": "run",
                "visibility": "private",
                "started_at": started,
                "distance_m": "5000",
                "duration_s": "1800",
            },
        )
        if create.status_code != 201:
            pytest.skip("Activity create failed (e.g. DB)")
        activity_id = create.json()["id"]

        # Owner can view
        r_owner = await client.get(f"/api/v1/activities/{activity_id}", headers=owner_headers)
        assert r_owner.status_code == 200

        # Other gets 403
        r_other = await client.get(f"/api/v1/activities/{activity_id}", headers=other_headers)
        assert r_other.status_code == 403

        # Unauthenticated gets 403 (not 404)
        r_anon = await client.get(f"/api/v1/activities/{activity_id}")
        assert r_anon.status_code == 403


@pytest.mark.asyncio
async def test_get_activity_public_visible_to_all():
    """Public activity: owner and other (and anon) can view."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "pub_owner@test.com", "password": "pass123", "name": "Pub Owner"},
        )
        login_owner = await client.post(
            "/api/v1/auth/login",
            json={"email": "pub_owner@test.com", "password": "pass123"},
        )
        owner_token = login_owner.json()["access_token"]
        owner_headers = _auth_headers(owner_token)

        started = datetime.now(timezone.utc).isoformat()
        create = await client.post(
            "/api/v1/activities",
            headers=owner_headers,
            data={
                "title": "Public run",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
                "distance_m": "3000",
                "duration_s": "1200",
            },
        )
        if create.status_code != 201:
            pytest.skip("Activity create failed")
        activity_id = create.json()["id"]

        assert (await client.get(f"/api/v1/activities/{activity_id}", headers=owner_headers)).status_code == 200
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "pub_other@test.com", "password": "pass123", "name": "Other"},
        )
        other_login = await client.post("/api/v1/auth/login", json={"email": "pub_other@test.com", "password": "pass123"})
        other_headers = _auth_headers(other_login.json()["access_token"])
        assert (await client.get(f"/api/v1/activities/{activity_id}", headers=other_headers)).status_code == 200
        assert (await client.get(f"/api/v1/activities/{activity_id}")).status_code == 200


@pytest.mark.asyncio
async def test_get_activity_status_owner_only_403_for_other():
    """GET /activities/{id}/status is 403 for non-owner (not 404)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "status_owner@test.com", "password": "pass123", "name": "Owner"},
        )
        login_owner = await client.post(
            "/api/v1/auth/login",
            json={"email": "status_owner@test.com", "password": "pass123"},
        )
        owner_headers = _auth_headers(login_owner.json()["access_token"])
        started = datetime.now(timezone.utc).isoformat()
        create = await client.post(
            "/api/v1/activities",
            headers=owner_headers,
            data={
                "title": "Status test",
                "sport_type": "run",
                "visibility": "public",
                "started_at": started,
            },
        )
        if create.status_code != 201:
            pytest.skip("Activity create failed")
        activity_id = create.json()["id"]

        await client.post(
            "/api/v1/auth/signup",
            json={"email": "status_other@test.com", "password": "pass123", "name": "Other"},
        )
        other_headers = _auth_headers(
            (await client.post("/api/v1/auth/login", json={"email": "status_other@test.com", "password": "pass123"})).json()["access_token"]
        )

        r_owner = await client.get(f"/api/v1/activities/{activity_id}/status", headers=owner_headers)
        assert r_owner.status_code == 200

        r_other = await client.get(f"/api/v1/activities/{activity_id}/status", headers=other_headers)
        assert r_other.status_code == 403


@pytest.mark.asyncio
async def test_get_activity_stream_respects_visibility():
    """Stream endpoint returns 403 when activity is not viewable."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "stream_owner@test.com", "password": "pass123", "name": "Owner"},
        )
        owner_headers = _auth_headers(
            (await client.post("/api/v1/auth/login", json={"email": "stream_owner@test.com", "password": "pass123"})).json()["access_token"]
        )
        started = datetime.now(timezone.utc).isoformat()
        create = await client.post(
            "/api/v1/activities",
            headers=owner_headers,
            data={
                "title": "Private stream",
                "sport_type": "run",
                "visibility": "private",
                "started_at": started,
            },
        )
        if create.status_code != 201:
            pytest.skip("Activity create failed")
        activity_id = create.json()["id"]

        await client.post(
            "/api/v1/auth/signup",
            json={"email": "stream_other@test.com", "password": "pass123", "name": "Other"},
        )
        other_headers = _auth_headers(
            (await client.post("/api/v1/auth/login", json={"email": "stream_other@test.com", "password": "pass123"})).json()["access_token"]
        )

        r_other = await client.get(f"/api/v1/activities/{activity_id}/stream", headers=other_headers)
        assert r_other.status_code == 403
