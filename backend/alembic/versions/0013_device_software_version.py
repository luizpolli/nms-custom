"""Add software_version column to devices table.

Revision ID: 0013_device_software_version
Revises: 0012_forwarding_targets
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_device_software_version"
down_revision = "0012_forwarding_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("software_version", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "software_version")
