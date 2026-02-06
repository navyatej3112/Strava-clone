"""User schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    bio: str | None = Field(None, max_length=2000)


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    bio: str | None = Field(None, max_length=2000)
    avatar_url: str | None = Field(None, max_length=512)


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    bio: str | None
    avatar_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    id: UUID
    name: str
    bio: str | None
    avatar_url: str | None

    model_config = {"from_attributes": True}
