"""Prometheus metrics for API, workers, queues, and telemetry ingestion."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, REGISTRY, generate_latest
from sqlalchemy import func, select

from app.database import async_session_factory
from app.models.kpi import KPI
from app.models.telemetry import TelemetryIngestionStat, TelemetryRawSample
from app.services.observability.heartbeat import get_all_worker_status


REQUEST_COUNT = Counter(
    "nms_api_requests_total",
    "Total API HTTP requests.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "nms_api_request_duration_seconds",
    "API request latency in seconds.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
DB_QUERY_LATENCY = Histogram(
    "nms_db_query_duration_seconds",
    "Database query latency in seconds for NMS self-observability probes.",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)


@dataclass(slots=True)
class MetricsSnapshot:
    kpi_rows: int = 0
    raw_telemetry_rows: int = 0
    telemetry_samples_total: int = 0
    telemetry_dropped_total: int = 0
    event_queue_depth: int = 0


async def observe_request(request, call_next: Callable[..., Awaitable]):
    """Starlette middleware hook that records request count and latency."""
    start = time.perf_counter()
    response = await call_next(request)
    path = getattr(request.scope.get("route"), "path", request.url.path)
    elapsed = time.perf_counter() - start
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
    return response


async def _event_queue_depth() -> int:
    try:
        import redis.asyncio as aioredis
        from app.config import settings

        client = aioredis.from_url(settings.redis_url, socket_timeout=2, decode_responses=True)
        try:
            return int(await client.xlen(settings.event_stream_name))
        finally:
            await client.aclose()
    except Exception:
        return 0


async def collect_metrics_snapshot() -> MetricsSnapshot:
    """Collect best-effort point-in-time metrics for Prometheus scraping."""
    snapshot = MetricsSnapshot(event_queue_depth=await _event_queue_depth())
    try:
        async with async_session_factory() as session:
            with DB_QUERY_LATENCY.labels("count_kpis").time():
                snapshot.kpi_rows = int((await session.execute(select(func.count()).select_from(KPI))).scalar_one() or 0)
            with DB_QUERY_LATENCY.labels("count_telemetry_raw").time():
                snapshot.raw_telemetry_rows = int(
                    (await session.execute(select(func.count()).select_from(TelemetryRawSample))).scalar_one() or 0
                )
            with DB_QUERY_LATENCY.labels("sum_telemetry_stats").time():
                stats = (
                    await session.execute(
                        select(
                            func.coalesce(func.sum(TelemetryIngestionStat.samples_total), 0),
                            func.coalesce(func.sum(TelemetryIngestionStat.dropped_total), 0),
                        )
                    )
                ).one()
            snapshot.telemetry_samples_total = int(stats[0] or 0)
            snapshot.telemetry_dropped_total = int(stats[1] or 0)
    except Exception as exc:
        # Metrics must never break health/scrape paths.
        logger.debug("Prometheus DB snapshot collection skipped: {}", exc)
    return snapshot


async def render_prometheus_metrics() -> tuple[bytes, str]:
    """Render Prometheus text exposition with dynamic DB/Redis gauges."""
    registry = CollectorRegistry()
    kpi_rows = Gauge("nms_kpi_rows", "Current KPI row count.", registry=registry)
    raw_rows = Gauge("nms_telemetry_raw_rows", "Current raw telemetry sample row count.", registry=registry)
    samples = Gauge("nms_telemetry_samples_total", "Telemetry samples accepted by collectors.", registry=registry)
    drops = Gauge("nms_telemetry_dropped_total", "Telemetry samples dropped by collectors.", registry=registry)
    queue_depth = Gauge("nms_event_queue_depth", "Redis Streams event queue depth.", ["stream"], registry=registry)
    worker_stale = Gauge("nms_worker_stale", "Worker stale status: 1 stale, 0 fresh.", ["kind"], registry=registry)
    worker_runs = Gauge("nms_worker_runs_total", "Worker heartbeat run counter.", ["kind"], registry=registry)
    worker_errors = Gauge("nms_worker_errors_total", "Worker heartbeat error counter.", ["kind"], registry=registry)

    snapshot = await collect_metrics_snapshot()
    kpi_rows.set(snapshot.kpi_rows)
    raw_rows.set(snapshot.raw_telemetry_rows)
    samples.set(snapshot.telemetry_samples_total)
    drops.set(snapshot.telemetry_dropped_total)

    from app.config import settings

    queue_depth.labels(settings.event_stream_name).set(snapshot.event_queue_depth)
    for worker in await get_all_worker_status():
        worker_stale.labels(worker.kind).set(1 if worker.is_stale else 0)
        worker_runs.labels(worker.kind).set(worker.runs_total)
        worker_errors.labels(worker.kind).set(worker.errors_total)

    return generate_latest(REGISTRY) + generate_latest(registry), CONTENT_TYPE_LATEST
