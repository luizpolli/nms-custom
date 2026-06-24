"""Orchestrates bulkstats ingestion: parse -> resolve device -> persist raw
samples -> promote catalog-enabled counters into the shared kpis table."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bulkstats import BulkstatsCounterCatalog, BulkstatsIngestionStat, BulkstatsRawSample
from app.models.device import Device
from app.models.kpi import KPI

from .disc_reasons import disc_reason_code, disc_reason_name
from .parser import BulkstatsRecord, parse_file

# Priority order for picking the single most useful identifier out of a
# record's labels (varies by group: gtpu/apn/etc use vpnname/servname, saegw
# prefixes them with "saegw-", card has only "card"). Falls back to the
# first available label when none of these match — the full label set is
# always preserved regardless, this is only a display/filter convenience.
_OBJECT_ID_LABEL_PRIORITY = ("servname", "saegw-servname", "vpnname", "saegw-vpnname", "card")


@dataclass(slots=True)
class IngestResult:
    source_ip: str
    device_id: uuid.UUID | None
    lines_parsed: int
    lines_failed: int
    raw_samples_written: int
    kpis_promoted: int
    unmatched_device: bool


_OBJECT_ID_MAX_LEN = 255  # matches BulkstatsRawSample/KPI.object_id column width


def _build_object_id(record: BulkstatsRecord) -> str | None:
    """Pick the most useful object_id for a record, truncated to fit the
    column. Some StarOS fields that fail the numeric check aren't short
    identifiers at all — e.g. `disc-reason-summary` is a ~500-char packed
    `code=count;code=count` blob — so this never raises on long values, it
    just truncates (the full, untruncated value always survives in `labels`)."""
    code = disc_reason_code(record.field_name)
    if code is not None:
        # disc-reason-<N> counters carry no labels of their own (the `system`
        # group line has no servname/vpnname) — without this, every reason
        # would chart as an unlabeled blended line instead of one per reason.
        return disc_reason_name(code)[:_OBJECT_ID_MAX_LEN]
    labels = record.labels
    if not labels:
        return None
    for key in _OBJECT_ID_LABEL_PRIORITY:
        if key in labels:
            return labels[key][:_OBJECT_ID_MAX_LEN]
    return next(iter(labels.values()))[:_OBJECT_ID_MAX_LEN]


async def _resolve_device(db: AsyncSession, ip_address: str) -> Device | None:
    stmt = select(Device).where(Device.ip_address == ip_address)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _load_enabled_catalog(db: AsyncSession) -> dict[tuple[str, str], BulkstatsCounterCatalog]:
    stmt = select(BulkstatsCounterCatalog).where(BulkstatsCounterCatalog.enabled.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return {(row.group, row.field_name): row for row in rows}


async def _record_ingestion_stat(
    db: AsyncSession,
    *,
    source_ip: str,
    device_id: uuid.UUID | None,
    lines_parsed: int,
    lines_failed: int,
    unmatched_device: bool,
    last_error: str | None,
) -> None:
    stmt = select(BulkstatsIngestionStat).where(BulkstatsIngestionStat.source_ip == source_ip)
    stat = (await db.execute(stmt)).scalar_one_or_none()
    if stat is None:
        # Column `default=0`s only apply on DB flush, not on construction —
        # initialize explicitly so the += below works on a fresh in-memory row.
        stat = BulkstatsIngestionStat(
            source_ip=source_ip, files_processed=0, lines_parsed=0, lines_failed=0,
        )
        db.add(stat)
    stat.device_id = device_id
    stat.files_processed += 1
    stat.lines_parsed += lines_parsed
    stat.lines_failed += lines_failed
    stat.unmatched_device = unmatched_device
    if last_error:
        stat.last_error = last_error
    stat.last_file_at = datetime.now(UTC)


def _build_raw_sample(
    record: BulkstatsRecord, *, device_id: uuid.UUID | None, source_ip: str, source_file: str
) -> BulkstatsRawSample:
    return BulkstatsRawSample(
        device_id=device_id,
        source_ip=source_ip,
        source_file=source_file,
        group=record.group,
        schema_name=record.schema_name,
        field_name=record.field_name,
        value=record.value,
        raw_value=record.raw_value,
        object_id=_build_object_id(record),
        labels=record.labels or None,
        timestamp=record.timestamp,
    )


def _build_kpi(record: BulkstatsRecord, *, device_id: uuid.UUID, catalog_entry: BulkstatsCounterCatalog) -> KPI:
    return KPI(
        device_id=device_id,
        # kpi_type doubles as the specific metric identifier throughout this
        # codebase (SNMP-sourced KPIs set kpi_type == metric_name too — see
        # _record_to_model in kpi/engine.py) so the existing
        # /devices/{id}/kpis(/aggregate) endpoints work for bulkstats data
        # with zero new query API. source_type="bulkstats" below is what
        # actually distinguishes the origin.
        kpi_type=catalog_entry.metric_name,
        metric_name=catalog_entry.metric_name,
        value=record.value if record.value is not None else 0.0,
        unit=catalog_entry.unit,
        source_type="bulkstats",
        object_type=catalog_entry.object_type,
        object_id=_build_object_id(record),
        labels=record.labels or None,
        timestamp=record.timestamp,
    )


async def ingest_file(db: AsyncSession, *, filename: str, content: str) -> IngestResult:
    """Parse one bulkstats file and persist raw samples + promoted KPIs.

    Caller is responsible for committing the session. Device resolution
    failure (unknown source IP) is not fatal — raw samples are still stored
    with device_id=None and unmatched_device=True is recorded on the
    ingestion stat for the admin to notice and fix inventory.
    """
    result = parse_file(content)
    device = await _resolve_device(db, result.header.ip_address)
    catalog = await _load_enabled_catalog(db)

    raw_rows: list[BulkstatsRawSample] = []
    kpi_rows: list[KPI] = []
    for record in result.records:
        raw_rows.append(
            _build_raw_sample(
                record,
                device_id=device.id if device else None,
                source_ip=result.header.ip_address,
                source_file=filename,
            )
        )
        catalog_entry = catalog.get((record.group, record.field_name))
        if catalog_entry is not None and device is not None and record.value is not None:
            kpi_rows.append(_build_kpi(record, device_id=device.id, catalog_entry=catalog_entry))

    db.add_all(raw_rows)
    db.add_all(kpi_rows)

    await _record_ingestion_stat(
        db,
        source_ip=result.header.ip_address,
        device_id=device.id if device else None,
        lines_parsed=result.lines_parsed,
        lines_failed=result.lines_failed,
        unmatched_device=device is None,
        last_error=result.errors[-1] if result.errors else None,
    )

    return IngestResult(
        source_ip=result.header.ip_address,
        device_id=device.id if device else None,
        lines_parsed=result.lines_parsed,
        lines_failed=result.lines_failed,
        raw_samples_written=len(raw_rows),
        kpis_promoted=len(kpi_rows),
        unmatched_device=device is None,
    )
