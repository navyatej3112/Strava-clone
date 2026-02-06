"""Tests for cookie-based refresh and rotation."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Signup then login
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "cookieuser@test.com", "password": "password123", "name": "Cookie User"},
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "cookieuser@test.com", "password": "password123"},
        )
        assert r.status_code == 200
        assert "refresh_token" in r.cookies or "set-cookie" in str(r.headers).lower()
        data = r.json()
        assert "access_token" in data
        assert data.get("refresh_token") is None


@pytest.mark.asyncio
async def test_refresh_rotates_and_returns_access():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "rotuser@test.com", "password": "password123", "name": "Rot User"},
        )
        login_r = await client.post(
            "/api/v1/auth/login",
            json={"email": "rotuser@test.com", "password": "password123"},
        )
        assert login_r.status_code == 200
        refresh_r = await client.post("/api/v1/auth/refresh")
        assert refresh_r.status_code == 200
        data = refresh_r.json()
        assert "access_token" in data


@pytest.mark.asyncio
async def test_logout_clears_cookie():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "logoutuser@test.com", "password": "password123", "name": "Logout User"},
        )
        await client.post(
            "/api/v1/auth/login",
            json={"email": "logoutuser@test.com", "password": "password123"},
        )
        logout_r = await client.post("/api/v1/auth/logout")
        assert logout_r.status_code == 200
        assert "refresh_token" not in logout_r.cookies or logout_r.cookies.get("refresh_token") == ""
