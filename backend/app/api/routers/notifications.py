"""Notifications: list (cursor), unread count, mark read."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import Notification
from app.models.notification import NotificationType
from app.schemas.notification import NotificationResponse, NotificationType as SchemaNotifType, MarkReadRequest
from app.api.deps import get_current_user, rate_limit_stub

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    cursor: UUID | None = Query(None),
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationResponse]:
    rate_limit_stub(request)
    q = (
        select(Notification)
        .where(Notification.recipient_user_id == current_user_id)
        .options(selectinload(Notification.actor))
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        cur = await db.get(Notification, cursor)
        if cur and cur.recipient_user_id == current_user_id:
            q = q.where(
                or_(
                    Notification.created_at < cur.created_at,
                    and_(Notification.created_at == cur.created_at, Notification.id < cur.id),
                )
            )
    result = await db.execute(q)
    items = list(result.scalars().unique().all())[:limit]
    return [
        NotificationResponse(
            id=n.id,
            recipient_user_id=n.recipient_user_id,
            actor_user_id=n.actor_user_id,
            type=SchemaNotifType(n.type.value),
            activity_id=n.activity_id,
            comment_id=n.comment_id,
            is_read=n.is_read,
            data=n.data,
            created_at=n.created_at,
            actor_name=n.actor.name if n.actor else None,
        )
        for n in items
    ]


@router.get("/unread-count")
async def unread_count(
    request: Request,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rate_limit_stub(request)
    from sqlalchemy import func
    r = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_user_id == current_user_id,
            Notification.is_read.is_(False),
        )
    )
    count = r.scalar() or 0
    return {"count": count}


@router.post("/mark-read")
async def mark_read(
    request: Request,
    body: MarkReadRequest,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rate_limit_stub(request)
    q = select(Notification).where(
        Notification.recipient_user_id == current_user_id,
        Notification.is_read.is_(False),
    )
    if body.mark_all:
        pass
    elif body.ids:
        q = q.where(Notification.id.in_(body.ids))
    else:
        return {"marked": 0}
    result = await db.execute(q)
    notifications = list(result.scalars().all())
    for n in notifications:
        n.is_read = True
    await db.commit()
    return {"marked": len(notifications)}

