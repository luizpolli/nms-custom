"""Retention and TimescaleDB helpers for KPI/telemetry time-series data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class RetentionPolicy:
    table: str
    timestamp_column: str
    keep_days: int


DEFAULT_RETENTION_POLICIES: tuple[RetentionPolicy, ...] = (
    RetentionPolicy("telemetry_raw_samples", "timestamp", 7),
    RetentionPolicy("kpis", "timestamp", 90),
)

_RETENTION_DELETE_SQL = {
    "telemetry_raw_samples": "DELETE FROM telemetry_raw_samples WHERE timestamp < now() - (:days * interval '1 day')",
    "kpis": "DELETE FROM kpis WHERE timestamp < now() - (:days * interval '1 day')",
}

_TIMESCALE_PK_SQL = {
    "kpis": (
        "ALTER TABLE kpis DROP CONSTRAINT IF EXISTS kpis_pkey",
        "ALTER TABLE kpis ADD PRIMARY KEY (id, timestamp)",
    ),
    "telemetry_raw_samples": (
        "ALTER TABLE telemetry_raw_samples DROP CONSTRAINT IF EXISTS telemetry_raw_samples_pkey",
        "ALTER TABLE telemetry_raw_samples ADD PRIMARY KEY (id, timestamp)",
    ),
}


async def enforce_retention(session: AsyncSession, policies: tuple[RetentionPolicy, ...] = DEFAULT_RETENTION_POLICIES) -> dict[str, int]:
    """Delete rows older than configured retention windows.

    This is a portable safety net. Timescale retention policies are installed
    separately when PostgreSQL/TimescaleDB is available.
    """
    deleted: dict[str, int] = {}
    for policy in policies:
        result = await session.execute(
            text(_RETENTION_DELETE_SQL[policy.table]),
            {"days": policy.keep_days},
        )
        deleted[policy.table] = int(result.rowcount or 0)  # type: ignore[attr-defined]  # rowcount on CursorResult
    return deleted


async def _ensure_timescale_primary_key(session: AsyncSession, table_name: str) -> bool:
    """Ensure table primary keys include Timescale's partition column."""
    result = await session.execute(
        text(
            """
            SELECT array_agg(a.attname ORDER BY a.attnum) AS columns
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
            WHERE c.contype = 'p' AND t.relname = :table_name
            """
        ),
        {"table_name": table_name},
    )
    columns = result.scalar_one_or_none() or []
    if "timestamp" in columns:
        return False
    for statement in _TIMESCALE_PK_SQL[table_name]:
        await session.execute(text(statement))
    return True


async def ensure_timescale_schema(session: AsyncSession) -> dict[str, str]:
    """Best-effort TimescaleDB setup for hypertables, retention, and aggregates.

    Existing dev databases may have plain PKs that Timescale cannot convert
    without a planned migration. Failures are reported as status strings instead
    of breaking startup.
    """
    status: dict[str, str] = {"checked_at": datetime.now(UTC).isoformat()}
    try:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        await session.commit()
        status["extension"] = "ok"
    except Exception as exc:  # pragma: no cover - depends on DB image/permissions
        await session.rollback()
        status["extension"] = f"skipped: {exc}"
        return status

    for table_name in ("kpis", "telemetry_raw_samples"):
        try:
            pk_changed = await _ensure_timescale_primary_key(session, table_name)
            await session.execute(
                text(
                    "SELECT create_hypertable(:table_name, 'timestamp', if_not_exists => TRUE, migrate_data => TRUE)"
                ),
                {"table_name": table_name},
            )
            await session.commit()
            status[f"primary_key.{table_name}"] = "id,timestamp" if pk_changed else "ok"
            status[f"hypertable.{table_name}"] = "ok"
        except Exception as exc:  # pragma: no cover - Timescale constraints vary with existing schema
            await session.rollback()
            status[f"hypertable.{table_name}"] = f"skipped: {exc}"
            logger.debug("Timescale hypertable setup skipped for {}: {}", table_name, exc)

    for policy in DEFAULT_RETENTION_POLICIES:
        try:
            await session.execute(text("SELECT remove_retention_policy(:table_name, if_exists => TRUE)"), {"table_name": policy.table})
            await session.execute(
                text("SELECT add_retention_policy(:table_name, (:days * interval '1 day'), if_not_exists => TRUE)"),
                {"table_name": policy.table, "days": policy.keep_days},
            )
            await session.commit()
            status[f"retention.{policy.table}"] = f"{policy.keep_days}d"
        except Exception as exc:  # pragma: no cover
            await session.rollback()
            status[f"retention.{policy.table}"] = f"skipped: {exc}"
            logger.debug("Timescale retention setup skipped for {}: {}", policy.table, exc)

    try:
        await session.execute(
            text(
                """
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
                WITH NO DATA
                """
            )
        )
        await session.commit()
        status["continuous_aggregate.kpi_hourly_rollups"] = "ok"
    except Exception as exc:  # pragma: no cover
        await session.rollback()
        status["continuous_aggregate.kpi_hourly_rollups"] = f"skipped: {exc}"
        logger.debug("Timescale continuous aggregate setup skipped: {}", exc)

    return status
