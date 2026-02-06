"""Activity model."""
import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ActivitySportType(str, enum.Enum):
    RUN = "run"
    RIDE = "ride"
    WALK = "walk"


class ActivityVisibility(str, enum.Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"


class ActivityStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sport_type: Mapped[ActivitySportType] = mapped_column(Enum(ActivitySportType), nullable=False)
    visibility: Mapped[ActivityVisibility] = mapped_column(Enum(ActivityVisibility), nullable=False, default=ActivityVisibility.PUBLIC)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Derived stats (computed from track or manual)
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)  # meters
    duration_s: Mapped[int | None] = mapped_column(nullable=True)  # seconds
    elevation_gain_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    calories: Mapped[int | None] = mapped_column(nullable=True)
    # Encoded polyline for map (from GPX/TCX or pasted)
    polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw file storage path (optional)
    raw_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[ActivityStatus] = mapped_column(Enum(ActivityStatus), nullable=False, default=ActivityStatus.READY)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # FairPlay: rank eligibility
    rank_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    rank_excluded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship("User", back_populates="activities")
    track_points: Mapped[list["TrackPoint"]] = relationship(
        "TrackPoint", back_populates="activity", cascade="all, delete-orphan", order_by="TrackPoint.time"
    )
    likes: Mapped[list["Like"]] = relationship("Like", back_populates="activity", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="activity", cascade="all, delete-orphan")
