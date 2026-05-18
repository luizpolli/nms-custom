"""service score history

Revision ID: 0006_service_score_history
Revises: 0005_service_dependencies
Create Date: 2026-05-18 12:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0006_service_score_history"
down_revision: Union[str, None] = "0005_service_dependencies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_score_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_id",
            UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("base_score", sa.Integer(), nullable=True),
        sa.Column("dependency_penalty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_state", sa.String(32), nullable=False, server_default="healthy"),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_service_score_history_service_id", "service_score_history", ["service_id"]
    )
    op.create_index(
        "ix_service_score_history_captured_at", "service_score_history", ["captured_at"]
    )
    op.create_index(
        "ix_service_score_history_service_captured",
        "service_score_history",
        ["service_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_service_score_history_service_captured", table_name="service_score_history"
    )
    op.drop_index("ix_service_score_history_captured_at", table_name="service_score_history")
    op.drop_index("ix_service_score_history_service_id", table_name="service_score_history")
    op.drop_table("service_score_history")
