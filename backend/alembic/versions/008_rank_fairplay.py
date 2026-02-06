"""FairPlay: rank eligibility flags on activities.

Revision ID: 008
Revises: 007
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("rank_eligible", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("activities", sa.Column("rank_excluded_reason", sa.Text(), nullable=True))
    op.add_column("activities", sa.Column("max_speed_kmh", sa.Float(), nullable=True))
    
    op.create_index("ix_activities_rank_eligible", "activities", ["rank_eligible"], unique=False)
    op.create_index("ix_activities_user_started", "activities", ["user_id", "started_at"], unique=False)
    op.create_index("ix_activities_sport_started", "activities", ["sport_type", "started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_activities_sport_started", table_name="activities")
    op.drop_index("ix_activities_user_started", table_name="activities")
    op.drop_index("ix_activities_rank_eligible", table_name="activities")
    
    op.drop_column("activities", "max_speed_kmh")
    op.drop_column("activities", "rank_excluded_reason")
    op.drop_column("activities", "rank_eligible")
