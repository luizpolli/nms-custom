"""command runs and schedules

Revision ID: 0008_command_runs_and_schedules
Revises: 0007_service_target_score
Create Date: 2026-05-19 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0008_command_runs_and_schedules"
down_revision: Union[str, None] = "0007_service_target_score"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "command_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commands.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_status", sa.Integer(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(64), nullable=False, server_default="manual"),
    )

    op.create_table(
        "command_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commands.id"), nullable=False),
        sa.Column("device_ids", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("tag", sa.String(128), nullable=True),
        sa.Column("cron_expr", sa.String(128), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("command_schedules")
    op.drop_table("command_runs")
