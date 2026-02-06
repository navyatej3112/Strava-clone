"""Like schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LikeResponse(BaseModel):
    id: UUID
    user_id: UUID
    activity_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
