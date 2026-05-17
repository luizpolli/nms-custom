"""Telemetry MVP ingestion and KPI normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kpi import KPI
from app.models.telemetry import TelemetryRawSample, TelemetrySensorPath
from app.schemas.telemetry import TelemetryIngestResult, TelemetrySampleIngest
from app.services.events import EventEnvelope, publish_event

SessionFactory = Callable[[], AsyncSession]


@dataclass(slots=True)
class NormalizedTelemetryMetric:
    metric_name: str
    kpi_type: str
    unit: str | None
    object_type: str
    labels: dict | None


def _fallback_metric_name(path: str) -> str:
    return path.strip("/").replace("/", ".") or "telemetry.sample"


def normalize_sample_to_kpi(
    sample: TelemetrySampleIngest,
    sensor_path: TelemetrySensorPath | None = None,
) -> KPI:
    """Convert one telemetry sample into the normalized KPI model."""
    metric = NormalizedTelemetryMetric(
        metric_name=sensor_path.metric_name if sensor_path else _fallback_metric_name(sample.path),
        kpi_type=sensor_path.kpi_type if sensor_path else _fallback_metric_name(sample.path)[:50],
        unit=sample.unit or (sensor_path.unit if sensor_path else None),
        object_type=sensor_path.object_type if sensor_path else sample.object_type,
        labels={**(sensor_path.labels or {}), **(sample.labels or {})} if sensor_path else sample.labels,
    )
    return KPI(
        device_id=sample.device_id,
        kpi_type=metric.kpi_type,
        metric_name=metric.metric_name,
        technology="telemetry",
        value=sample.value,
        unit=metric.unit,
        kpi_area="telemetry",
        source_type="telemetry",
        object_type=metric.object_type,
        object_id=sample.object_id,
        quality=sample.quality,
        labels=metric.labels,
        meta={"path": sample.path, "collector_id": str(sample.collector_id or "")},
        timestamp=sample.timestamp,
    )


class TelemetryIngestionService:
    """Persist raw telemetry samples and normalize them into KPI rows."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sf = session_factory

    async def ingest_sample(self, sample: TelemetrySampleIngest) -> TelemetryIngestResult:
        async with self._sf() as session:
            sensor_path = await self._find_sensor_path(session, sample.path)
            raw = TelemetryRawSample(
                collector_id=sample.collector_id,
                subscription_id=sample.subscription_id,
                device_id=sample.device_id,
                path=sample.path,
                value=sample.value,
                unit=sample.unit,
                quality=sample.quality,
                object_type=sample.object_type,
                object_id=sample.object_id,
                labels=sample.labels,
                raw_payload=sample.raw_payload,
                timestamp=sample.timestamp,
            )
            kpi = normalize_sample_to_kpi(sample, sensor_path)
            session.add(raw)
            session.add(kpi)
            await session.flush()
            await session.commit()

            stream_id = await publish_event(
                EventEnvelope(
                    event_type="telemetry.sample.normalized",
                    source="telemetry",
                    device_id=str(sample.device_id),
                    object_type=kpi.object_type,
                    object_id=kpi.object_id,
                    severity="info" if sample.quality == "good" else "warning",
                    payload={
                        "path": sample.path,
                        "metric_name": kpi.metric_name,
                        "kpi_type": kpi.kpi_type,
                        "value": sample.value,
                        "unit": kpi.unit,
                        "quality": sample.quality,
                    },
                )
            )
            return TelemetryIngestResult(
                raw_sample_id=raw.id,
                kpi_id=kpi.id,
                metric_name=kpi.metric_name or kpi.kpi_type,
                kpi_type=kpi.kpi_type,
                event_published=stream_id is not None,
            )

    async def _find_sensor_path(
        self, session: AsyncSession, path: str
    ) -> TelemetrySensorPath | None:
        result = await session.execute(
            select(TelemetrySensorPath)
            .where(TelemetrySensorPath.path == path, TelemetrySensorPath.enabled.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none()
