"""User rank fields for PaceRank.

Revision ID: 006
Revises: 005
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("rank_tier", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("rank_score", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("rank_range_days", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("users", sa.Column("rank_last_computed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("rank_progress", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("rank_next_tier", sa.String(length=50), nullable=True))

    op.create_index("ix_users_rank_score", "users", ["rank_score"], unique=False)
    op.create_index("ix_users_rank_tier", "users", ["rank_tier"], unique=False)
    op.create_index("ix_users_rank_last_computed_at", "users", ["rank_last_computed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_rank_last_computed_at", table_name="users")
    op.drop_index("ix_users_rank_tier", table_name="users")
    op.drop_index("ix_users_rank_score", table_name="users")

    op.drop_column("users", "rank_next_tier")
    op.drop_column("users", "rank_progress")
    op.drop_column("users", "rank_last_computed_at")
    op.drop_column("users", "rank_range_days")
    op.drop_column("users", "rank_score")
    op.drop_column("users", "rank_tier")

