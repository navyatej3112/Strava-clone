"""Track point for elevation chart and splits."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TrackPoint(Base):
    __tablename__ = "track_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lat: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    lon: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    elevation_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    # Cumulative distance from start (meters), optional for splits
    cumulative_distance_m: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    activity: Mapped["Activity"] = relationship("Activity", back_populates="track_points")
