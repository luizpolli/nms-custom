"""service dependency modeling

Revision ID: 0005_service_dependencies
Revises: 0004_services
Create Date: 2026-05-18 12:15:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0005_service_dependencies"
down_revision: Union[str, None] = "0004_services"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_dependencies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_service_id", UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_service_id", UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dependency_type", sa.String(50), nullable=False, server_default="depends_on"),
        sa.Column("direction", sa.String(50), nullable=False, server_default="source_to_target"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_critical", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_service_id", "target_service_id", name="uq_service_dependency_edge"),
    )
    op.create_index("ix_service_dependencies_source_service_id", "service_dependencies", ["source_service_id"])
    op.create_index("ix_service_dependencies_target_service_id", "service_dependencies", ["target_service_id"])


def downgrade() -> None:
    op.drop_index("ix_service_dependencies_target_service_id", table_name="service_dependencies")
    op.drop_index("ix_service_dependencies_source_service_id", table_name="service_dependencies")
    op.drop_table("service_dependencies")
