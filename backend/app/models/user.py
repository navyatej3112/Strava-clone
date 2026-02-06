"""User model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # PaceRank fields (runner ranking)
    rank_tier: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    rank_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    rank_range_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    rank_last_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    rank_progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_next_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    activities: Mapped[list["Activity"]] = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    followers: Mapped[list["Follow"]] = relationship("Follow", foreign_keys="Follow.followed_id", back_populates="followed")
    following: Mapped[list["Follow"]] = relationship("Follow", foreign_keys="Follow.follower_id", back_populates="follower")
    likes: Mapped[list["Like"]] = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    refresh_sessions: Mapped[list["RefreshSession"]] = relationship("RefreshSession", back_populates="user", cascade="all, delete-orphan")
