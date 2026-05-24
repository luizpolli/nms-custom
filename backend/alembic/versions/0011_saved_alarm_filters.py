"""Add saved alarm filters

Revision ID: 0011_saved_alarm_filters
Revises: 0010_service_dependency_richer_modeling
Create Date: 2026-05-23 22:15:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011_saved_alarm_filters"
down_revision: Union[str, None] = "0010_service_dependency_richer_modeling"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_alarm_filters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_alarm_filters_owner", "saved_alarm_filters", ["owner"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_saved_alarm_filters_owner", table_name="saved_alarm_filters")
    op.drop_table("saved_alarm_filters")
