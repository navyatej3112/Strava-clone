"""Audit: add indexes for feed/ordering and ensure stable sort.

Revision ID: 002
Revises: 001
Create Date: 2025-02-05

- activities: index created_at, composite (created_at, id) for stable feed ordering
- follows/likes/comments: already have unique constraints and FK CASCADE in 001
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f("ix_activities_created_at"), "activities", ["created_at"], unique=False)
    op.create_index(
        op.f("ix_activities_created_at_id"),
        "activities",
        ["created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_activities_created_at_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_created_at"), table_name="activities")
