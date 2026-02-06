"""Segment and SegmentEffort models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text, Boolean, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    polyline: Mapped[str] = mapped_column(Text, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    owner: Mapped["User"] = relationship("User", back_populates="segments")
    efforts: Mapped[list["SegmentEffort"]] = relationship(
        "SegmentEffort", back_populates="segment", cascade="all, delete-orphan"
    )


class SegmentEffort(Base):
    __tablename__ = "segment_efforts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Copy of activity visibility at compute time
    visibility: Mapped[str] = mapped_column(Text, nullable=False)
    effort_time_s: Mapped[int] = mapped_column(Integer, nullable=False)
    effort_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    avg_speed_kmh: Mapped[float] = mapped_column(Float, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    segment: Mapped[Segment] = relationship("Segment", back_populates="efforts")
    # We don't need explicit relationships to Activity/User here for now.

