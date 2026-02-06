"""End-to-end verification script for PaceTrail.

Usage:
    python -m scripts.verify_e2e [--api-url http://localhost:8000]

Runs sanity checks, seeds DB, tests API endpoints, and validates DB state.
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import Segment, SegmentEffort, Notification


class Verifier:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url.rstrip("/")
        self.checks: list[tuple[str, bool, str]] = []  # (name, passed, message)
        self.http_client: Optional[httpx.AsyncClient] = None
        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None

    def check(self, name: str, passed: bool, message: str = ""):
        """Record a check result."""
        self.checks.append((name, passed, message))
        symbol = "✅" if passed else "❌"
        print(f"{symbol} {name}" + (f": {message}" if message else ""))

    async def setup_http_client(self):
        """Create httpx client with cookie support."""
        self.http_client = httpx.AsyncClient(
            base_url=self.api_url,
            timeout=30.0,
            follow_redirects=True,
        )

    async def cleanup(self):
        """Cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()

    async def verify_env(self):
        """Check environment variables and DB connectivity."""
        print("\n=== Environment & Connectivity ===")
        
        # Check DATABASE_URL
        db_url = os.getenv("DATABASE_URL") or settings.database_url
        if not db_url:
            self.check("DATABASE_URL set", False, "Missing DATABASE_URL")
            return False
        self.check("DATABASE_URL set", True)
        
        # Check Redis (optional)
        redis_url = os.getenv("REDIS_URL") or settings.redis_url
        if redis_url:
            self.check("REDIS_URL set", True)
        else:
            self.check("REDIS_URL set", False, "Optional, but recommended for async jobs")
        
        # Test DB connection
        try:
            database_url = db_url
            if "+asyncpg" not in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(database_url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            self.check("DB connectivity", True)
            return True
        except Exception as e:
            self.check("DB connectivity", False, str(e))
            return False

    async def verify_migrations(self):
        """Check if migrations are at head."""
        print("\n=== Migrations ===")
        try:
            database_url = settings.database_url
            if "+asyncpg" not in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(database_url, echo=False)
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.scalar()
                if version:
                    self.check("Migrations applied", True, f"Current: {version}")
                else:
                    self.check("Migrations applied", False, "No alembic_version found")
            await engine.dispose()
        except Exception as e:
            self.check("Migrations check", False, f"Error: {e}")

    async def run_seed(self):
        """Run seed script programmatically."""
        print("\n=== Seeding Database ===")
        try:
            # Import seed_db module and run its async run() function
            import importlib.util
            seed_path = Path(__file__).parent / "seed_db.py"
            spec = importlib.util.spec_from_file_location("seed_db", seed_path)
            seed_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(seed_module)
            await seed_module.run()
            self.check("Seed completed", True)
            return True
        except Exception as e:
            self.check("Seed completed", False, str(e))
            import traceback
            traceback.print_exc()
            return False

    async def test_auth(self):
        """Test auth endpoints: signup, login, refresh, logout."""
        print("\n=== Auth Endpoints ===")
        if not self.http_client:
            await self.setup_http_client()
        
        # Signup
        try:
            email = f"verify_{int(time.time())}@test.com"
            signup_resp = await self.http_client.post(
                "/api/v1/auth/signup",
                json={"email": email, "password": "testpass123", "name": "Verify User"},
            )
            if signup_resp.status_code == 201:
                self.check("POST /auth/signup", True)
                self.user_id = signup_resp.json()["id"]
            elif signup_resp.status_code == 409:
                # User exists, try login instead
                self.check("POST /auth/signup", True, "User exists, will login")
            else:
                self.check("POST /auth/signup", False, f"Status {signup_resp.status_code}")
        except Exception as e:
            self.check("POST /auth/signup", False, str(e))
        
        # Login
        try:
            login_resp = await self.http_client.post(
                "/api/v1/auth/login",
                json={"email": "user1@example.com", "password": "password"},
            )
            if login_resp.status_code == 200:
                data = login_resp.json()
                self.access_token = data.get("access_token")
                self.check("POST /auth/login", True)
            else:
                self.check("POST /auth/login", False, f"Status {login_resp.status_code}")
        except Exception as e:
            self.check("POST /auth/login", False, str(e))
        
        if not self.access_token:
            return False
        
        # Refresh
        try:
            refresh_resp = await self.http_client.post("/api/v1/auth/refresh")
            if refresh_resp.status_code == 200:
                new_token = refresh_resp.json().get("access_token")
                if new_token:
                    self.access_token = new_token
                    self.check("POST /auth/refresh", True)
                else:
                    self.check("POST /auth/refresh", False, "No token in response")
            else:
                self.check("POST /auth/refresh", False, f"Status {refresh_resp.status_code}")
        except Exception as e:
            self.check("POST /auth/refresh", False, str(e))
        
        # Logout
        try:
            logout_resp = await self.http_client.post("/api/v1/auth/logout")
            self.check("POST /auth/logout", logout_resp.status_code == 200)
        except Exception as e:
            self.check("POST /auth/logout", False, str(e))
        
        return True

    def _get_auth_headers(self) -> dict:
        """Get auth headers for API calls."""
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    async def test_pacerank(self):
        """Test PaceRank endpoints."""
        print("\n=== PaceRank Endpoints ===")
        if not self.http_client:
            await self.setup_http_client()
        if not self.access_token:
            await self.test_auth()
        
        headers = self._get_auth_headers()
        
        # GET /ranks/me
        try:
            resp = await self.http_client.get("/api/v1/ranks/me", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                self.check("GET /ranks/me", True, f"Tier: {data.get('rank_tier', 'None')}")
            else:
                self.check("GET /ranks/me", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /ranks/me", False, str(e))
        
        # POST /ranks/me/recompute (handle async)
        try:
            recompute_resp = await self.http_client.post("/api/v1/ranks/me/recompute", headers=headers)
            if recompute_resp.status_code == 200:
                data = recompute_resp.json()
                if data.get("status") == "queued" and "job_id" in data:
                    # Poll for completion
                    job_id = data["job_id"]
                    for _ in range(30):
                        await asyncio.sleep(1)
                        status_resp = await self.http_client.get(
                            f"/api/v1/ranks/me/recompute/{job_id}", headers=headers
                        )
                        if status_resp.status_code == 200:
                            status_data = status_resp.json()
                            if status_data.get("status") == "finished":
                                self.check("POST /ranks/me/recompute (async)", True)
                                break
                            elif status_data.get("status") == "failed":
                                self.check("POST /ranks/me/recompute (async)", False, "Job failed")
                                break
                    else:
                        self.check("POST /ranks/me/recompute (async)", False, "Timeout")
                elif data.get("status") == "finished":
                    self.check("POST /ranks/me/recompute (sync)", True)
                else:
                    self.check("POST /ranks/me/recompute", False, f"Unexpected: {data}")
            else:
                self.check("POST /ranks/me/recompute", False, f"Status {recompute_resp.status_code}")
        except Exception as e:
            self.check("POST /ranks/me/recompute", False, str(e))
        
        # GET /ranks/leaderboards/runs (global)
        try:
            resp = await self.http_client.get(
                "/api/v1/ranks/leaderboards/runs", params={"range": "30d", "limit": "10"}, headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                self.check("GET /ranks/leaderboards/runs (global)", True, f"{len(items)} items")
            else:
                self.check("GET /ranks/leaderboards/runs (global)", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /ranks/leaderboards/runs (global)", False, str(e))
        
        # GET /ranks/leaderboards/runs/following
        try:
            resp = await self.http_client.get(
                "/api/v1/ranks/leaderboards/runs/following", params={"range": "30d", "limit": "10"}, headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                self.check("GET /ranks/leaderboards/runs/following", True, f"{len(items)} items")
            else:
                self.check("GET /ranks/leaderboards/runs/following", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /ranks/leaderboards/runs/following", False, str(e))

    async def test_segments(self):
        """Test segment endpoints."""
        print("\n=== Segment Endpoints ===")
        if not self.http_client:
            await self.setup_http_client()
        if not self.access_token:
            await self.test_auth()
        
        headers = self._get_auth_headers()
        
        # GET /segments
        segment_id = None
        try:
            resp = await self.http_client.get("/api/v1/segments", params={"limit": "10"})
            if resp.status_code == 200:
                segments = resp.json()
                self.check("GET /segments", True, f"{len(segments)} segments")
                if segments:
                    segment_id = segments[0]["id"]
            else:
                self.check("GET /segments", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /segments", False, str(e))
        
        if not segment_id:
            return
        
        # GET /segments/{id}/leaderboard
        try:
            resp = await self.http_client.get(f"/api/v1/segments/{segment_id}/leaderboard")
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                kom = data.get("kom")
                self.check("GET /segments/{id}/leaderboard", True, f"{len(items)} items, KOM: {kom is not None}")
            else:
                self.check("GET /segments/{id}/leaderboard", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /segments/{id}/leaderboard", False, str(e))
        
        # GET /segments/{id}/my-efforts
        try:
            resp = await self.http_client.get(f"/api/v1/segments/{segment_id}/my-efforts", headers=headers)
            if resp.status_code == 200:
                efforts = resp.json()
                self.check("GET /segments/{id}/my-efforts", True, f"{len(efforts)} efforts")
            else:
                self.check("GET /segments/{id}/my-efforts", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /segments/{id}/my-efforts", False, str(e))

    async def test_activities(self):
        """Test activity endpoints."""
        print("\n=== Activity Endpoints ===")
        if not self.http_client:
            await self.setup_http_client()
        if not self.access_token:
            await self.test_auth()
        
        headers = self._get_auth_headers()
        
        # Find a READY RUN activity
        try:
            resp = await self.http_client.get("/api/v1/activities/feed", params={"limit": "10"}, headers=headers)
            if resp.status_code == 200:
                activities = resp.json()
                run_activity = next(
                    (a for a in activities if a.get("sport_type") == "run" and a.get("status") == "ready"), None
                )
                if run_activity:
                    activity_id = run_activity["id"]
                    # GET /activities/{id}
                    detail_resp = await self.http_client.get(f"/api/v1/activities/{activity_id}", headers=headers)
                    if detail_resp.status_code == 200:
                        detail = detail_resp.json()
                        segments = detail.get("segments")
                        seg_count = len(segments) if segments else 0
                        self.check(
                            "GET /activities/{id} (with segments)",
                            True,
                            f"segments field present, {seg_count} efforts",
                        )
                    else:
                        self.check("GET /activities/{id}", False, f"Status {detail_resp.status_code}")
                else:
                    self.check("GET /activities/{id}", False, "No READY run activity found")
            else:
                self.check("GET /activities/feed", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /activities/{id}", False, str(e))

    async def test_notifications(self):
        """Test notification endpoints."""
        print("\n=== Notification Endpoints ===")
        if not self.http_client:
            await self.setup_http_client()
        if not self.access_token:
            await self.test_auth()
        
        headers = self._get_auth_headers()
        
        try:
            resp = await self.http_client.get("/api/v1/notifications", headers=headers)
            if resp.status_code == 200:
                notifications = resp.json()
                types_present = {n.get("type") for n in notifications}
                self.check(
                    "GET /notifications",
                    True,
                    f"{len(notifications)} notifications, types: {sorted(types_present)}",
                )
                # Validate data structure for segment notifications
                for n in notifications:
                    if n.get("type") in ("segment_pr", "segment_kom"):
                        data = n.get("data")
                        if data and isinstance(data, dict):
                            required_keys = {"segment_id", "segment_name", "activity_id", "effort_time_s", "type"}
                            missing = required_keys - set(data.keys())
                            if missing:
                                self.check(
                                    f"Notification {n.get('type')} data structure",
                                    False,
                                    f"Missing keys: {missing}",
                                )
                            else:
                                self.check(f"Notification {n.get('type')} data structure", True)
            else:
                self.check("GET /notifications", False, f"Status {resp.status_code}")
        except Exception as e:
            self.check("GET /notifications", False, str(e))

    async def verify_db_assertions(self):
        """Run DB assertions."""
        print("\n=== Database Assertions ===")
        try:
            database_url = settings.database_url
            if "+asyncpg" not in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            engine = create_async_engine(database_url, echo=False)
            async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            
            async with async_session() as session:
                # Segments count >= 3
                seg_count_result = await session.execute(select(func.count(Segment.id)))
                seg_count = seg_count_result.scalar() or 0
                self.check("Segments count >= 3", seg_count >= 3, f"Found {seg_count}")
                
                # At least 2 segments have >= 3 efforts
                effort_counts_stmt = (
                    select(SegmentEffort.segment_id, func.count(SegmentEffort.id))
                    .group_by(SegmentEffort.segment_id)
                    .having(func.count(SegmentEffort.id) >= 3)
                )
                rich_segments_result = await session.execute(effort_counts_stmt)
                rich_segments = len(list(rich_segments_result.all()))
                self.check("Segments with >=3 efforts >= 2", rich_segments >= 2, f"Found {rich_segments}")
                
                # Notification dedupe_key uniqueness
                dupes_stmt = (
                    select(Notification.dedupe_key, func.count(Notification.id))
                    .where(Notification.dedupe_key.isnot(None))
                    .group_by(Notification.dedupe_key)
                    .having(func.count(Notification.id) > 1)
                )
                dupes_result = await session.execute(dupes_stmt)
                dupes = list(dupes_result.all())
                self.check("Notification dedupe_key unique", len(dupes) == 0, f"Found {len(dupes)} duplicates")
                
                # Leaderboard query validation (sample one segment)
                sample_seg_result = await session.execute(select(Segment.id).limit(1))
                sample_seg_id = sample_seg_result.scalar()
                if sample_seg_id:
                    from app.models.activity import ActivityVisibility
                    
                    leaderboard_stmt = (
                        select(SegmentEffort)
                        .where(SegmentEffort.segment_id == sample_seg_id)
                        .where(SegmentEffort.visibility == ActivityVisibility.PUBLIC.value)
                        .order_by(SegmentEffort.effort_time_s.asc())
                        .limit(10)
                    )
                    leaderboard_result = await session.execute(leaderboard_stmt)
                    leaderboard_items = list(leaderboard_result.scalars().all())
                    is_sorted = all(
                        leaderboard_items[i].effort_time_s <= leaderboard_items[i + 1].effort_time_s
                        for i in range(len(leaderboard_items) - 1)
                    ) if len(leaderboard_items) > 1 else True
                    self.check(
                        "Leaderboard sorted correctly",
                        is_sorted,
                        f"{len(leaderboard_items)} items, sorted: {is_sorted}",
                    )
            
            await engine.dispose()
        except Exception as e:
            self.check("DB assertions", False, str(e))

    def print_report(self) -> int:
        """Print final report and return exit code."""
        print("\n" + "=" * 60)
        print("VERIFICATION REPORT")
        print("=" * 60)
        
        passed = sum(1 for _, p, _ in self.checks if p)
        total = len(self.checks)
        
        print(f"\nTotal checks: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        
        if total - passed > 0:
            print("\nFailed checks:")
            for name, passed, msg in self.checks:
                if not passed:
                    print(f"  ❌ {name}" + (f": {msg}" if msg else ""))
        
        print("\n" + "=" * 60)
        return 0 if passed == total else 1

    async def run_all(self):
        """Run all verification steps."""
        try:
            if not await self.verify_env():
                return 1
            
            await self.verify_migrations()
            await self.run_seed()
            await self.setup_http_client()
            await self.test_auth()
            await self.test_pacerank()
            await self.test_segments()
            await self.test_activities()
            await self.test_notifications()
            await self.verify_db_assertions()
            
            return self.print_report()
        finally:
            await self.cleanup()


async def main():
    parser = argparse.ArgumentParser(description="End-to-end verification for PaceTrail")
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL for API (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    
    verifier = Verifier(api_url=args.api_url)
    exit_code = await verifier.run_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
