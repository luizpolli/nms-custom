"""timescale retention and KPI rollups

Revision ID: 0a7d92a4b5c1
Revises: 0002_telemetry_mvp
Create Date: 2026-05-17 02:05:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0a7d92a4b5c1"
down_revision: Union[str, None] = "0002_telemetry_mvp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Install TimescaleDB helpers when the extension is available.

    Dev databases created before this migration may have unique constraints that
    Timescale refuses to convert in-place. Each block is intentionally
    best-effort so migrations keep working on plain PostgreSQL while production
    deployments can use Timescale-native retention and continuous aggregates.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
                WHERE c.contype = 'p' AND t.relname = 'kpis' AND a.attname = 'timestamp'
            ) THEN
                ALTER TABLE kpis DROP CONSTRAINT IF EXISTS kpis_pkey;
                ALTER TABLE kpis ADD PRIMARY KEY (id, timestamp);
            END IF;
            PERFORM create_hypertable('kpis', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping kpis hypertable setup: %', SQLERRM;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
                WHERE c.contype = 'p' AND t.relname = 'telemetry_raw_samples' AND a.attname = 'timestamp'
            ) THEN
                ALTER TABLE telemetry_raw_samples DROP CONSTRAINT IF EXISTS telemetry_raw_samples_pkey;
                ALTER TABLE telemetry_raw_samples ADD PRIMARY KEY (id, timestamp);
            END IF;
            PERFORM create_hypertable('telemetry_raw_samples', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping telemetry_raw_samples hypertable setup: %', SQLERRM;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            PERFORM remove_retention_policy('telemetry_raw_samples', if_exists => TRUE);
            PERFORM add_retention_policy('telemetry_raw_samples', INTERVAL '7 days', if_not_exists => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping telemetry_raw_samples retention policy: %', SQLERRM;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            PERFORM remove_retention_policy('kpis', if_exists => TRUE);
            PERFORM add_retention_policy('kpis', INTERVAL '90 days', if_not_exists => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping kpis retention policy: %', SQLERRM;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE MATERIALIZED VIEW IF NOT EXISTS kpi_hourly_rollups
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', timestamp) AS bucket,
                device_id,
                kpi_type,
                metric_name,
                object_type,
                object_id,
                avg(value) AS avg_value,
                min(value) AS min_value,
                max(value) AS max_value,
                count(*) AS sample_count
            FROM kpis
            GROUP BY bucket, device_id, kpi_type, metric_name, object_type, object_id
            WITH NO DATA;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping kpi_hourly_rollups continuous aggregate: %', SQLERRM;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS kpi_hourly_rollups")
    op.execute(
        """
        DO $$
        BEGIN
            PERFORM remove_retention_policy('telemetry_raw_samples', if_exists => TRUE);
            PERFORM remove_retention_policy('kpis', if_exists => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Skipping Timescale retention policy removal: %', SQLERRM;
        END $$;
        """
    )
