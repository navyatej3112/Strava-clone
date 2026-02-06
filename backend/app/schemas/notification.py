"""Notification schemas."""
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class NotificationType(str, Enum):
    FOLLOW = "follow"
    LIKE = "like"
    COMMENT = "comment"
    RANK_UP = "rank_up"


class NotificationResponse(BaseModel):
    id: UUID
    recipient_user_id: UUID
    actor_user_id: UUID
    type: NotificationType
    activity_id: UUID | None
    comment_id: UUID | None
    is_read: bool
    data: dict | None = None
    created_at: datetime
    actor_name: str | None = None

    model_config = {"from_attributes": True}


class MarkReadRequest(BaseModel):
    ids: list[UUID] | None = None
    mark_all: bool = False
