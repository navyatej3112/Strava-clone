"""RQ job: recompute PaceRank for a user."""
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import asyncio

from app.core.config import settings
from app.services.rank_service import RankService


def recompute_rank_job(user_id_str: str, range_days: int = 30) -> dict:
    """Recompute PaceRank for a user. Run in RQ worker."""
    user_id = UUID(user_id_str)
    
    # Create async engine and session
    database_url = settings.database_url
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async def _recompute():
        async with async_session() as async_db:
            service = RankService(async_db)
            resp = await service.recompute_user_rank(user_id, range_days=range_days)
            await async_db.commit()
            return resp
    
    # Run async function in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    resp = loop.run_until_complete(_recompute())
    
    return {
        "tier": resp.rank_tier,
        "score": resp.rank_score,
        "progress": resp.rank_progress,
        "next_tier": resp.rank_next_tier,
        "last_computed_at": resp.rank_last_computed_at.isoformat() if resp.rank_last_computed_at else None,
    }
