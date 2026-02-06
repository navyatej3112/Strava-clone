"""Recompute PaceRank for all users.

Usage:

    python -m scripts.recompute_ranks
"""
import asyncio

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models import User  # noqa: E402
from app.services.rank_service import RankService  # noqa: E402


async def run() -> None:
    database_url = settings.database_url
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(select(User))
        users = list(result.scalars().all())
        if not users:
            print("No users found; nothing to recompute.")
            return
        service = RankService(session)
        for u in users:
            resp = await service.recompute_user_rank(u.id, range_days=30)
            print(f"{u.email}: {resp.rank_tier} ({resp.rank_score:.1f})")
        await session.commit()
        print(f"Recomputed ranks for {len(users)} users.")


if __name__ == "__main__":
    asyncio.run(run())

