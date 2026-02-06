"""Comment schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .user import UserPublic


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    id: UUID
    user_id: UUID
    activity_id: UUID
    body: str
    created_at: datetime
    user: UserPublic | None = None

    model_config = {"from_attributes": True}
