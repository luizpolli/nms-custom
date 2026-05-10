"""Pure mapping functions: SNMP results → KPIRecord dicts ready for DB insert.

Counter wrap detection:
  - If the new counter value is less than the previous value, a wrap is assumed.
  - 32-bit wrap threshold: max value 2^32 - 1  (ifInOctets uses 32-bit counters)
  - 64-bit wrap threshold: max value 2^64 - 1  (ifHCInOctets uses 64-bit counters)
  - The counter is assumed to be 32-bit if its previous value fits within 32-bit range.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from app.services.snmp.engine import InterfaceRow

_COUNTER32_MAX: int = 2**32 - 1
_COUNTER64_MAX: int = 2**64 - 1


@dataclass(slots=True)
class KPIRecord:
    """One KPI measurement ready for DB insert."""

    device_id: uuid.UUID
    kpi_type: str
    technology: str | None
    value: float
    unit: str | None
    kpi_area: str | None
    # FIXME: 'metadata' collides with SQLAlchemy's reserved DeclarativeBase attribute.
    # Use getattr(kpi_row, 'metadata') or raw INSERT when writing to the KPI table.
    metadata: dict | None
    timestamp: datetime


@dataclass(slots=True)
class InterfaceSnapshot:
    """Counter snapshot for one interface at a point in time."""

    if_index: int
    in_octets: int | None
    out_octets: int | None
    in_errors: int | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _delta_rate(new: int | None, prev: int | None, elapsed: float, prev_val: int | None) -> float | None:
    """Compute per-second rate handling counter wrap. Returns None if inputs are invalid."""
    if new is None or prev is None or elapsed <= 0:
        return None
    if new >= prev:
        return (new - prev) / elapsed
    # Counter wrapped — detect 32-bit vs 64-bit by looking at the previous value
    wrap_max = _COUNTER32_MAX if (prev_val is not None and prev_val <= _COUNTER32_MAX) else _COUNTER64_MAX
    wrapped_delta = (wrap_max - prev) + new + 1
    logger.debug("Counter wrap detected: prev={} new={} wrap_max={}", prev, new, wrap_max)
    return wrapped_delta / elapsed


def map_cpu_memory(
    device_id: uuid.UUID,
    cpu_mem: dict[str, float | None],
    timestamp: datetime | None = None,
) -> list[KPIRecord]:
    """Map get_cpu_memory() result into KPIRecords."""
    ts = timestamp or datetime.now(timezone.utc)
    records: list[KPIRecord] = []

    mappings: list[tuple[str, str, str | None, str | None]] = [
        ("cpu_5min",      "cpu_5min",      "snmp",   "%"),
        ("cpu_1min",      "cpu_1min",      "snmp",   "%"),
        ("mem_used_pct",  "mem_used_pct",  "snmp",   "%"),
    ]
    for src_key, kpi_type, technology, unit in mappings:
        val = cpu_mem.get(src_key)
        if val is None:
            continue
        records.append(KPIRecord(
            device_id=device_id,
            kpi_type=kpi_type,
            technology=technology,
            value=float(val),
            unit=unit,
            kpi_area="performance",
            metadata=None,
            timestamp=ts,
        ))
    return records


def map_interfaces(
    device_id: uuid.UUID,
    interfaces: dict[int, "InterfaceRow"],
    timestamp: datetime | None = None,
    previous_snapshot: dict[int, InterfaceSnapshot] | None = None,
) -> tuple[list[KPIRecord], dict[int, InterfaceSnapshot]]:
    """Map get_interfaces() result into KPIRecords.

    Returns (records, new_snapshot). When previous_snapshot is None, counter-based
    KPIs are stored as raw snapshots (kpi_type ending in _raw) instead of rates.
    """
    ts = timestamp or datetime.now(timezone.utc)
    records: list[KPIRecord] = []
    new_snapshot: dict[int, InterfaceSnapshot] = {}

    for idx, row in interfaces.items():
        descr = row.descr or f"if{idx}"
        meta = {"if_index": idx, "if_descr": descr}
        if row.alias:
            meta["if_alias"] = row.alias

        # Operational status — always emit, no delta needed
        if row.oper_status is not None:
            records.append(KPIRecord(
                device_id=device_id,
                kpi_type="if_oper_status",
                technology="snmp",
                value=float(row.oper_status),
                unit=None,
                kpi_area="availability",
                metadata={**meta, "admin_status": row.admin_status},
                timestamp=ts,
            ))

        # Build current snapshot for delta calculations
        snap = InterfaceSnapshot(
            if_index=idx,
            in_octets=row.in_octets,
            out_octets=row.out_octets,
            in_errors=row.in_errors,
            timestamp=ts,
        )
        new_snapshot[idx] = snap

        prev = previous_snapshot.get(idx) if previous_snapshot else None

        if prev is None:
            # No previous snapshot — emit raw counter values
            _emit_raw(records, device_id, "if_in_octets_raw", row.in_octets, "bytes", meta, ts)
            _emit_raw(records, device_id, "if_out_octets_raw", row.out_octets, "bytes", meta, ts)
            _emit_raw(records, device_id, "if_in_errors_raw", row.in_errors, "errors", meta, ts)
        else:
            elapsed = (ts - prev.timestamp).total_seconds()
            _emit_rate(records, device_id, "if_in_octets_rate", row.in_octets,
                       prev.in_octets, elapsed, meta, ts, "bytes/s")
            _emit_rate(records, device_id, "if_out_octets_rate", row.out_octets,
                       prev.out_octets, elapsed, meta, ts, "bytes/s")
            _emit_rate(records, device_id, "if_in_errors_rate", row.in_errors,
                       prev.in_errors, elapsed, meta, ts, "errors/s")

    return records, new_snapshot


def _emit_raw(
    records: list[KPIRecord],
    device_id: uuid.UUID,
    kpi_type: str,
    value: int | None,
    unit: str,
    meta: dict,
    ts: datetime,
) -> None:
    if value is None:
        return
    records.append(KPIRecord(
        device_id=device_id,
        kpi_type=kpi_type,
        technology="snmp",
        value=float(value),
        unit=unit,
        kpi_area="traffic",
        metadata=meta,
        timestamp=ts,
    ))


def _emit_rate(
    records: list[KPIRecord],
    device_id: uuid.UUID,
    kpi_type: str,
    new_val: int | None,
    prev_val: int | None,
    elapsed: float,
    meta: dict,
    ts: datetime,
    unit: str,
) -> None:
    rate = _delta_rate(new_val, prev_val, elapsed, prev_val)
    if rate is None:
        return
    records.append(KPIRecord(
        device_id=device_id,
        kpi_type=kpi_type,
        technology="snmp",
        value=rate,
        unit=unit,
        kpi_area="traffic",
        metadata=meta,
        timestamp=ts,
    ))
