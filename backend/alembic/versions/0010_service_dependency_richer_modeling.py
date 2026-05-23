"""P2: richer service dependency modeling — direction_override, evidence column

Revision ID: 0010_service_dependency_richer_modeling
Revises: 0009_settings_system_network_alarms
Create Date: 2026-05-19 16:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010_service_dependency_richer_modeling"
down_revision: Union[str, None] = "0009_settings_system_network_alarms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add direction_override to service_dependencies
    op.add_column(
        "service_dependencies",
        sa.Column(
            "direction_override",
            sa.String(50),
            nullable=False,
            server_default="auto",
        ),
    )

    # Add evidence JSON column to service_score_history
    op.add_column(
        "service_score_history",
        sa.Column(
            "evidence",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("service_score_history", "evidence")
    op.drop_column("service_dependencies", "direction_override")
