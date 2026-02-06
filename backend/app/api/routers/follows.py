"""Follow/unfollow users."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.follow_service import FollowService
from app.schemas import UserPublic
from app.api.deps import get_current_user, rate_limit_stub

router = APIRouter(prefix="/follows", tags=["follows"])


@router.post("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def follow_user(
    request: Request,
    user_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rate_limit_stub(request)
    service = FollowService(db)
    ok = await service.follow(current_user_id, user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    from app.services.notification_service import NotificationService
    await NotificationService(db).create_follow(recipient_user_id=user_id, actor_user_id=current_user_id)
    await db.commit()


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    request: Request,
    user_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rate_limit_stub(request)
    await FollowService(db).unfollow(current_user_id, user_id)


@router.get("/{user_id}/following", response_model=bool)
async def is_following(
    request: Request,
    user_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> bool:
    rate_limit_stub(request)
    return await FollowService(db).is_following(current_user_id, user_id)


@router.get("/me/following", response_model=list[UserPublic])
async def list_following(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserPublic]:
    rate_limit_stub(request)
    return await FollowService(db).get_following(current_user_id, limit=limit, offset=offset)


@router.get("/me/followers", response_model=list[UserPublic])
async def list_followers(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserPublic]:
    rate_limit_stub(request)
    return await FollowService(db).get_followers(current_user_id, limit=limit, offset=offset)
