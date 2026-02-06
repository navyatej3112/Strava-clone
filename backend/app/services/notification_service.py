"""Create notifications and list/mark read."""
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification
from app.models.notification import NotificationType


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_follow(self, recipient_user_id: UUID, actor_user_id: UUID) -> None:
        if recipient_user_id == actor_user_id:
            return
        n = Notification(
            recipient_user_id=recipient_user_id,
            actor_user_id=actor_user_id,
            type=NotificationType.FOLLOW,
        )
        self.db.add(n)

    async def create_like(self, recipient_user_id: UUID, actor_user_id: UUID, activity_id: UUID) -> None:
        if recipient_user_id == actor_user_id:
            return
        n = Notification(
            recipient_user_id=recipient_user_id,
            actor_user_id=actor_user_id,
            type=NotificationType.LIKE,
            activity_id=activity_id,
        )
        self.db.add(n)

    async def create_comment(
        self, recipient_user_id: UUID, actor_user_id: UUID, activity_id: UUID, comment_id: UUID
    ) -> None:
        if recipient_user_id == actor_user_id:
            return
        n = Notification(
            recipient_user_id=recipient_user_id,
            actor_user_id=actor_user_id,
            type=NotificationType.COMMENT,
            activity_id=activity_id,
            comment_id=comment_id,
        )
        self.db.add(n)

    async def create_segment_pr(
        self,
        recipient_user_id: UUID,
        segment_id: UUID,
        segment_name: str,
        effort_time_s: int,
        activity_id: UUID,
    ) -> None:
        """Create a notification for a new personal record on a segment."""
        n = Notification(
            recipient_user_id=recipient_user_id,
            actor_user_id=recipient_user_id,
            type=NotificationType.SEGMENT_PR,
            activity_id=activity_id,
            data={
                "segment_id": str(segment_id),
                "segment_name": segment_name,
                "activity_id": str(activity_id),
                "effort_time_s": effort_time_s,
                "type": "pr",
            },
        )
        self.db.add(n)

    async def create_segment_kom(
        self,
        recipient_user_id: UUID,
        segment_id: UUID,
        segment_name: str,
        effort_time_s: int,
        activity_id: UUID,
    ) -> None:
        """Create a notification for taking KOM on a segment (public efforts only)."""
        n = Notification(
            recipient_user_id=recipient_user_id,
            actor_user_id=recipient_user_id,
            type=NotificationType.SEGMENT_KOM,
            activity_id=activity_id,
            data={
                "segment_id": str(segment_id),
                "segment_name": segment_name,
                "activity_id": str(activity_id),
                "effort_time_s": effort_time_s,
                "type": "kom",
            },
        )
        self.db.add(n)
