"""Add physical inventory component table.

Revision ID: 0014_physical_inventory_components
Revises: 0013_device_software_version
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_physical_inventory_components"
down_revision = "0013_device_software_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "physical_inventory_components",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("physical_index", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("vendor_type", sa.String(length=255), nullable=True),
        sa.Column("contained_physical_index", sa.Integer(), nullable=True),
        sa.Column("physical_class", sa.Integer(), nullable=True),
        sa.Column("parent_rel_pos", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("hardware_version", sa.String(length=100), nullable=True),
        sa.Column("firmware_version", sa.String(length=100), nullable=True),
        sa.Column("software_version", sa.String(length=100), nullable=True),
        sa.Column("serial_number", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("alias", sa.String(length=255), nullable=True),
        sa.Column("asset_id", sa.String(length=255), nullable=True),
        sa.Column("is_fru", sa.Boolean(), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_physical_inventory_device_index",
        "physical_inventory_components",
        ["device_id", "physical_index"],
        unique=True,
    )
    op.create_index(
        "ix_physical_inventory_device_class",
        "physical_inventory_components",
        ["device_id", "physical_class"],
        unique=False,
    )
    op.create_index("ix_physical_inventory_serial", "physical_inventory_components", ["serial_number"], unique=False)
    op.create_index(
        op.f("ix_physical_inventory_components_device_id"),
        "physical_inventory_components",
        ["device_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_physical_inventory_components_device_id"), table_name="physical_inventory_components")
    op.drop_index("ix_physical_inventory_serial", table_name="physical_inventory_components")
    op.drop_index("ix_physical_inventory_device_class", table_name="physical_inventory_components")
    op.drop_index("ix_physical_inventory_device_index", table_name="physical_inventory_components")
    op.drop_table("physical_inventory_components")
