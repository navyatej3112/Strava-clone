"""Add dedupe_key to notifications for idempotent segment PR/KOM notifications.

Revision ID: 011
Revises: 010
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    # Unique index on dedupe_key where it's not null (allows multiple NULLs)
    op.create_index(
        "ix_notifications_dedupe_key",
        "notifications",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_dedupe_key", table_name="notifications")
    op.drop_column("notifications", "dedupe_key")
