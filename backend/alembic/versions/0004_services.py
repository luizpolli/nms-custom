"""service-level impact modeling

Revision ID: 0004_services
Revises: 0a7d92a4b5c1
Create Date: 2026-05-17 02:25:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004_services"
down_revision: Union[str, None] = "0a7d92a4b5c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("kind", sa.String(50), nullable=False, server_default="other"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "service_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_id",
            UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "interface_id",
            UUID(as_uuid=True),
            sa.ForeignKey("interfaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_service_members_service_id", "service_members", ["service_id"])
    op.create_index("ix_service_members_device_id", "service_members", ["device_id"])
    op.create_index("ix_service_members_interface_id", "service_members", ["interface_id"])


def downgrade() -> None:
    op.drop_index("ix_service_members_interface_id", table_name="service_members")
    op.drop_index("ix_service_members_device_id", table_name="service_members")
    op.drop_index("ix_service_members_service_id", table_name="service_members")
    op.drop_table("service_members")
    op.drop_table("services")
