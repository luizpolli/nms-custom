"""Add system/network-devices/alarms-events settings keys (no schema change — reuses system_settings table)

Revision ID: 0009_settings_system_network_alarms
Revises: 0008_command_runs_and_schedules
Create Date: 2026-05-19 15:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_settings_system_network_alarms"
down_revision: Union[str, None] = "0008_command_runs_and_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The new system/network_devices/alarms_events settings are stored as JSON rows
# in the existing system_settings table.  No DDL change is required; the rows
# are created on first GET/PUT by the API layer.  This migration records the
# intent and keeps the revision chain intact.


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Remove the three new setting rows if they were seeded.
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM system_settings WHERE key IN ('system', 'network_devices', 'alarms_events')")
    )
