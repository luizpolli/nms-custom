"""telemetry mvp schema

Revision ID: 0002_telemetry_mvp
Revises: d861265823a6
Create Date: 2026-05-17 00:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_telemetry_mvp"
down_revision: Union[str, None] = "d861265823a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telemetry_collectors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("collector_type", sa.String(length=50), nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telemetry_collectors_name"), "telemetry_collectors", ["name"], unique=True)

    op.create_table(
        "telemetry_sensor_paths",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("platform_family", sa.String(length=100), nullable=True),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("metric_name", sa.String(length=255), nullable=False),
        sa.Column("kpi_type", sa.String(length=50), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("object_type", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telemetry_sensor_paths_kpi_type"), "telemetry_sensor_paths", ["kpi_type"], unique=False)
    op.create_index(op.f("ix_telemetry_sensor_paths_metric_name"), "telemetry_sensor_paths", ["metric_name"], unique=False)
    op.create_index(op.f("ix_telemetry_sensor_paths_path"), "telemetry_sensor_paths", ["path"], unique=False)
    op.create_index("ix_telemetry_sensor_vendor_path", "telemetry_sensor_paths", ["vendor", "path"], unique=False)

    op.create_table(
        "telemetry_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("collector_id", sa.UUID(), nullable=True),
        sa.Column("device_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("sample_interval_ms", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("last_sample_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["collector_id"], ["telemetry_collectors.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telemetry_subscriptions_path"), "telemetry_subscriptions", ["path"], unique=False)
    op.create_index("ix_telemetry_subscriptions_device_path", "telemetry_subscriptions", ["device_id", "path"], unique=False)

    op.create_table(
        "telemetry_ingestion_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("collector_id", sa.UUID(), nullable=True),
        sa.Column("samples_total", sa.Integer(), nullable=False),
        sa.Column("dropped_total", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_sample_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["collector_id"], ["telemetry_collectors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "telemetry_raw_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("collector_id", sa.UUID(), nullable=True),
        sa.Column("subscription_id", sa.UUID(), nullable=True),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("quality", sa.String(length=30), nullable=False),
        sa.Column("object_type", sa.String(length=50), nullable=False),
        sa.Column("object_id", sa.String(length=255), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["collector_id"], ["telemetry_collectors.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["telemetry_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_telemetry_raw_samples_path"), "telemetry_raw_samples", ["path"], unique=False)
    op.create_index("ix_telemetry_raw_device_timestamp", "telemetry_raw_samples", ["device_id", "timestamp"], unique=False)
    op.create_index("ix_telemetry_raw_path_timestamp", "telemetry_raw_samples", ["path", "timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_telemetry_raw_path_timestamp", table_name="telemetry_raw_samples")
    op.drop_index("ix_telemetry_raw_device_timestamp", table_name="telemetry_raw_samples")
    op.drop_index(op.f("ix_telemetry_raw_samples_path"), table_name="telemetry_raw_samples")
    op.drop_table("telemetry_raw_samples")
    op.drop_table("telemetry_ingestion_stats")
    op.drop_index("ix_telemetry_subscriptions_device_path", table_name="telemetry_subscriptions")
    op.drop_index(op.f("ix_telemetry_subscriptions_path"), table_name="telemetry_subscriptions")
    op.drop_table("telemetry_subscriptions")
    op.drop_index("ix_telemetry_sensor_vendor_path", table_name="telemetry_sensor_paths")
    op.drop_index(op.f("ix_telemetry_sensor_paths_path"), table_name="telemetry_sensor_paths")
    op.drop_index(op.f("ix_telemetry_sensor_paths_metric_name"), table_name="telemetry_sensor_paths")
    op.drop_index(op.f("ix_telemetry_sensor_paths_kpi_type"), table_name="telemetry_sensor_paths")
    op.drop_table("telemetry_sensor_paths")
    op.drop_index(op.f("ix_telemetry_collectors_name"), table_name="telemetry_collectors")
    op.drop_table("telemetry_collectors")
