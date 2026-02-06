"""Segments and segment efforts.

Revision ID: 009
Revises: 007
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("polyline", sa.Text(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_segments_owner_user_id", "segments", ["owner_user_id"], unique=False)
    op.create_index("ix_segments_is_public", "segments", ["is_public"], unique=False)
    op.create_index("ix_segments_created_at", "segments", ["created_at"], unique=False)

    op.create_table(
        "segment_efforts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("segments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("effort_time_s", sa.Integer(), nullable=False),
        sa.Column("effort_distance_m", sa.Float(), nullable=False),
        sa.Column("avg_speed_kmh", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("segment_id", "activity_id", name="uq_segment_efforts_segment_activity"),
    )
    op.create_index(
        "ix_segment_efforts_segment_time",
        "segment_efforts",
        ["segment_id", "effort_time_s"],
        unique=False,
    )
    op.create_index(
        "ix_segment_efforts_user_segment",
        "segment_efforts",
        ["user_id", "segment_id"],
        unique=False,
    )
    op.create_index(
        "ix_segment_efforts_started_at",
        "segment_efforts",
        ["started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_segment_efforts_started_at", table_name="segment_efforts")
    op.drop_index("ix_segment_efforts_user_segment", table_name="segment_efforts")
    op.drop_index("ix_segment_efforts_segment_time", table_name="segment_efforts")
    op.drop_table("segment_efforts")

    op.drop_index("ix_segments_created_at", table_name="segments")
    op.drop_index("ix_segments_is_public", table_name="segments")
    op.drop_index("ix_segments_owner_user_id", table_name="segments")
    op.drop_table("segments")

