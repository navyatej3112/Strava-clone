"""Comments on activities."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import Comment, Activity
from app.schemas import CommentCreate, CommentResponse
from app.api.deps import get_current_user, get_current_user_optional, rate_limit_stub

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("/activities/{activity_id}", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    request: Request,
    activity_id: UUID,
    data: CommentCreate,
    current_user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    rate_limit_stub(request)
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    comment = Comment(activity_id=activity_id, user_id=current_user_id, body=data.body)
    db.add(comment)
    await db.flush()
    from app.services.notification_service import NotificationService
    await NotificationService(db).create_comment(
        recipient_user_id=activity.user_id,
        actor_user_id=current_user_id,
        activity_id=activity_id,
        comment_id=comment.id,
    )
    await db.commit()
    await db.refresh(comment)
    await db.refresh(comment, ["user"])
    from app.schemas.user import UserPublic
    return CommentResponse(
        id=comment.id,
        user_id=comment.user_id,
        activity_id=comment.activity_id,
        body=comment.body,
        created_at=comment.created_at,
        user=UserPublic.model_validate(comment.user) if comment.user else None,
    )


@router.get("/activities/{activity_id}", response_model=list[CommentResponse])
async def list_comments(
    request: Request,
    activity_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[CommentResponse]:
    rate_limit_stub(request)
    result = await db.execute(
        select(Comment)
        .where(Comment.activity_id == activity_id)
        .options(selectinload(Comment.user))
        .order_by(Comment.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    comments = result.scalars().unique().all()
    from app.schemas.user import UserPublic
    return [
        CommentResponse(
            id=c.id,
            user_id=c.user_id,
            activity_id=c.activity_id,
            body=c.body,
            created_at=c.created_at,
            user=UserPublic.model_validate(c.user) if c.user else None,
        )
        for c in comments
    ]
