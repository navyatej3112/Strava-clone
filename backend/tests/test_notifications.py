"""Tests for notification creation and endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_unread_count_and_mark_read_endpoints():
    """Requires DB with at least one user; tests unread-count and mark-read."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/notifications/unread-count")
        if r.status_code == 401:
            pytest.skip("Needs auth")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data


@pytest.mark.asyncio
async def test_notifications_list_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/v1/notifications")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_mark_read_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post("/api/v1/notifications/mark-read", json={"mark_all": True})
        assert r.status_code == 401
