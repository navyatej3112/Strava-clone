"""Follow schemas."""
from uuid import UUID

from pydantic import BaseModel

from .user import UserPublic


class FollowResponse(BaseModel):
    follower_id: UUID
    followed_id: UUID
    followed: UserPublic | None = None

    model_config = {"from_attributes": True}
