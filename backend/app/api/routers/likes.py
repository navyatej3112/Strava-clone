"""Like/unlike activities."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app.core.database import get_db
from app.models import Like, Activity
from app.api.deps import get_current_user, rate_limit_stub

router = APIRouter(prefix="/likes", tags=["likes"])


@router.post("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def like_activity(
    request: Request,
    activity_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rate_limit_stub(request)
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    existing = await db.execute(select(Like).where(Like.activity_id == activity_id, Like.user_id == current_user_id))
    if existing.scalar_one_or_none():
        return  # idempotent
    like = Like(activity_id=activity_id, user_id=current_user_id)
    db.add(like)
    await db.flush()
    from app.services.notification_service import NotificationService
    await NotificationService(db).create_like(
        recipient_user_id=activity.user_id,
        actor_user_id=current_user_id,
        activity_id=activity_id,
    )
    await db.commit()


@router.delete("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_activity(
    request: Request,
    activity_id: UUID,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rate_limit_stub(request)
    await db.execute(delete(Like).where(Like.activity_id == activity_id, Like.user_id == current_user_id))
    await db.commit()
