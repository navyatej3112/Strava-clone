"""Users: me, update profile, search, get by id."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.user_service import UserService
from app.schemas import UserResponse, UserUpdate, UserPublic
from app.api.deps import get_current_user, get_current_user_optional, rate_limit_stub

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    request: Request,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    rate_limit_stub(request)
    service = UserService(db)
    me = await service.get_me(current_user_id)
    if not me:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return me


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: Request,
    data: UserUpdate,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    rate_limit_stub(request)
    service = UserService(db)
    updated = await service.update_me(current_user_id, data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated


@router.get("/search", response_model=list[UserPublic])
async def search_users(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user_id: UUID | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[UserPublic]:
    rate_limit_stub(request)
    service = UserService(db)
    return await service.search_users(q, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    rate_limit_stub(request)
    service = UserService(db)
    user = await service.get_public(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
