"""Add activity status and error_message for processing pipeline.

Revision ID: 003
Revises: 002
Create Date: 2025-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    activitystatus = sa.Enum("draft", "processing", "ready", "failed", name="activitystatus")
    activitystatus.create(op.get_bind(), checkfirst=True)
    op.add_column("activities", sa.Column("status", activitystatus, nullable=False, server_default="ready"))
    op.add_column("activities", sa.Column("error_message", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "error_message")
    op.drop_column("activities", "status")
    op.execute("DROP TYPE activitystatus")
