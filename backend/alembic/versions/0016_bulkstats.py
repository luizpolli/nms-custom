"""Add bulkstats tables: counter catalog, raw samples (hypertable), ingestion stats.

Revision ID: 0016_bulkstats
Revises: 0015_config_backups
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_bulkstats"
down_revision = "0015_config_backups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bulkstats_counter_catalog",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("metric_name", sa.String(length=255), nullable=False),
        sa.Column("kpi_type", sa.String(length=50), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("object_type", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bulkstats_catalog_group_field", "bulkstats_counter_catalog", ["group", "field_name"], unique=True
    )
    op.create_index(
        op.f("ix_bulkstats_counter_catalog_group"), "bulkstats_counter_catalog", ["group"]
    )
    op.create_index(
        op.f("ix_bulkstats_counter_catalog_field_name"), "bulkstats_counter_catalog", ["field_name"]
    )

    op.create_table(
        "bulkstats_raw_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=True),
        sa.Column("source_ip", sa.String(length=45), nullable=False),
        sa.Column("source_file", sa.String(length=512), nullable=False),
        sa.Column("group", sa.String(length=100), nullable=False),
        sa.Column("schema_name", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("raw_value", sa.String(length=255), nullable=True),
        sa.Column("object_id", sa.String(length=255), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bulkstats_raw_device_timestamp", "bulkstats_raw_samples", ["device_id", "timestamp"]
    )
    op.create_index(
        "ix_bulkstats_raw_group_field_timestamp",
        "bulkstats_raw_samples",
        ["group", "field_name", "timestamp"],
    )
    op.create_index(op.f("ix_bulkstats_raw_samples_source_ip"), "bulkstats_raw_samples", ["source_ip"])
    op.create_index(op.f("ix_bulkstats_raw_samples_group"), "bulkstats_raw_samples", ["group"])
    op.create_index(op.f("ix_bulkstats_raw_samples_field_name"), "bulkstats_raw_samples", ["field_name"])

    op.create_table(
        "bulkstats_ingestion_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_ip", sa.String(length=45), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=True),
        sa.Column("files_processed", sa.Integer(), nullable=False),
        sa.Column("lines_parsed", sa.Integer(), nullable=False),
        sa.Column("lines_failed", sa.Integer(), nullable=False),
        sa.Column("unmatched_device", sa.Boolean(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_file_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pulled_filenames", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_ip"),
    )
    op.create_index(
        op.f("ix_bulkstats_ingestion_stats_source_ip"), "bulkstats_ingestion_stats", ["source_ip"]
    )

    # TimescaleDB hypertable + 30-day retention for the raw firehose table,
    # mirroring telemetry_raw_samples in 0003_timescale_retention_metrics.py.
    # Best-effort: plain PostgreSQL dev databases without the extension just
    # skip this block and keep a normal table.
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE bulkstats_raw_samples DROP CONSTRAINT IF EXISTS bulkstats_raw_samples_pkey;
            ALTER TABLE bulkstats_raw_samples ADD PRIMARY KEY (id, timestamp);
            PERFORM create_hypertable('bulkstats_raw_samples', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);
            PERFORM remove_retention_policy('bulkstats_raw_samples', if_exists => TRUE);
            PERFORM add_retention_policy('bulkstats_raw_samples', INTERVAL '30 days', if_not_exists => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping bulkstats_raw_samples hypertable/retention setup: %', SQLERRM;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            PERFORM remove_retention_policy('bulkstats_raw_samples', if_exists => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping bulkstats_raw_samples retention policy removal: %', SQLERRM;
        END $$;
        """
    )
    op.drop_table("bulkstats_ingestion_stats")
    op.drop_table("bulkstats_raw_samples")
    op.drop_table("bulkstats_counter_catalog")
