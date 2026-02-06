"""API dependencies: DB session, current user, rate limit stub."""
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.config import settings
from app.repositories.user_repository import UserRepository

# Optional: OAuth2PasswordBearer for OpenAPI; we use Bearer token
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> UUID | None:
    if not credentials or credentials.credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        uid = UUID(user_id)
    except ValueError:
        return None
    repo = UserRepository(db)
    user = await repo.get_by_id(uid)
    if not user:
        return None
    return uid


async def get_current_user(
    current_user_id: UUID | None = Depends(get_current_user_optional),
) -> UUID:
    if current_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user_id


# Rate limit stub: just check a simple in-memory dict (or Redis in production)
# For MVP we skip actual limiting but provide the interface.
_rate_limit_store: dict[str, list[float]] = {}


def rate_limit_stub(request: Request) -> None:
    """Stub: in production use Redis + sliding window. No-op for now."""
    # TODO: implement with Redis when available
    # key = request.client.host if request.client else "unknown"
    # now = time.time()
    # window = 60  # 1 minute
    # ... enforce settings.rate_limit_per_minute
    pass
