"""Add config_backups table for config snapshots and golden baselines.

Revision ID: 0015_config_backups
Revises: 0014_physical_inventory_components
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_config_backups"
down_revision = "0014_physical_inventory_components"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_backups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("collected_by", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_config_backups_device_kind_created",
        "config_backups",
        ["device_id", "kind", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_config_backups_device_id"), "config_backups", ["device_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_config_backups_device_id"), table_name="config_backups")
    op.drop_index("ix_config_backups_device_kind_created", table_name="config_backups")
    op.drop_table("config_backups")
