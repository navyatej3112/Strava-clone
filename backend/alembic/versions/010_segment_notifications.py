"""Segment PR/COM notifications.

Revision ID: 010
Revises: 009
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new notification types for segments
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'segment_pr'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'segment_kom'")


def downgrade() -> None:
    # Enum value removal is not trivial; leave as-is.
    pass

