"""PaceRank history snapshots and rank-up notifications.

Revision ID: 007
Revises: 006
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add rank_up to NotificationType enum
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'rank_up'")
    
    # Add data JSONB column to notifications
    op.add_column("notifications", sa.Column("data", postgresql.JSONB, nullable=True))
    
    # Create rank_snapshots table
    op.create_table(
        "rank_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("tier_id", sa.String(length=50), nullable=False),
        sa.Column("tier_name", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "snapshot_date", "scope", name="uq_rank_snapshots_user_date_scope"),
    )
    
    op.create_index("ix_rank_snapshots_user_date", "rank_snapshots", ["user_id", "snapshot_date"], unique=False)
    op.create_index("ix_rank_snapshots_scope_date", "rank_snapshots", ["scope", "snapshot_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rank_snapshots_scope_date", table_name="rank_snapshots")
    op.drop_index("ix_rank_snapshots_user_date", table_name="rank_snapshots")
    op.drop_table("rank_snapshots")
    
    op.drop_column("notifications", "data")
    # Note: Cannot remove enum value easily in PostgreSQL, so we leave it
