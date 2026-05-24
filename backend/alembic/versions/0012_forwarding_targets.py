"""event forwarding targets

Revision ID: 0012_forwarding_targets
Revises: 0011_saved_alarm_filters
Create Date: 2026-05-23 22:11:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012_forwarding_targets"
down_revision: Union[str, None] = "0011_saved_alarm_filters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forwarding_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("protocol", sa.String(20), nullable=False),
        sa.Column("target_host", sa.String(255), nullable=False),
        sa.Column("target_port", sa.Integer(), nullable=False),
        sa.Column("event_types", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("severity_filter", sa.String(20), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_forwarding_targets_name"),
    )
    op.create_index("ix_forwarding_targets_name", "forwarding_targets", ["name"])


def downgrade() -> None:
    op.drop_index("ix_forwarding_targets_name", table_name="forwarding_targets")
    op.drop_table("forwarding_targets")
