"""Unit tests for app.services.kpi.mapper — pure functions, no DB."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from app.services.kpi.mapper import (
    KPIRecord,
    InterfaceSnapshot,
    _COUNTER32_MAX,
    _COUNTER64_MAX,
    _delta_rate,
    map_cpu_memory,
    map_interfaces,
)
from app.services.snmp.engine import InterfaceRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dev() -> uuid.UUID:
    return uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


def _ts(offset_seconds: float = 0) -> datetime:
    return datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)


def _make_row(
    if_index: int = 1,
    in_octets: int | None = 1000,
    out_octets: int | None = 2000,
    in_errors: int | None = 0,
    oper_status: int | None = 1,
    descr: str = "GigabitEthernet0/0",
) -> InterfaceRow:
    return InterfaceRow(
        if_index=if_index,
        descr=descr,
        oper_status=oper_status,
        in_octets=in_octets,
        out_octets=out_octets,
        in_errors=in_errors,
    )


# ---------------------------------------------------------------------------
# _delta_rate
# ---------------------------------------------------------------------------

class TestDeltaRate:
    def test_normal_increase(self) -> None:
        rate = _delta_rate(new=2000, prev=1000, elapsed=10.0, prev_val=1000)
        assert rate == pytest.approx(100.0)

    def test_zero_elapsed_returns_none(self) -> None:
        assert _delta_rate(new=2000, prev=1000, elapsed=0.0, prev_val=1000) is None

    def test_none_new_returns_none(self) -> None:
        assert _delta_rate(new=None, prev=1000, elapsed=10.0, prev_val=1000) is None

    def test_none_prev_returns_none(self) -> None:
        assert _delta_rate(new=2000, prev=None, elapsed=10.0, prev_val=None) is None

    def test_counter32_wrap(self) -> None:
        prev = _COUNTER32_MAX - 100
        new = 899
        elapsed = 10.0
        # expected delta = 100 + 899 + 1 = 1000 => rate = 100.0
        rate = _delta_rate(new=new, prev=prev, elapsed=elapsed, prev_val=prev)
        assert rate == pytest.approx(100.0)

    def test_counter64_wrap(self) -> None:
        prev = _COUNTER64_MAX - 100
        new = 899
        elapsed = 10.0
        rate = _delta_rate(new=new, prev=prev, elapsed=elapsed, prev_val=prev)
        assert rate == pytest.approx(100.0)

    def test_32bit_vs_64bit_detection(self) -> None:
        """prev within 32-bit range => wraps at 2^32, not 2^64."""
        prev32 = 10
        prev64 = _COUNTER32_MAX + 10
        new = 5
        elapsed = 1.0
        rate32 = _delta_rate(new=new, prev=prev32, elapsed=elapsed, prev_val=prev32)
        rate64 = _delta_rate(new=new, prev=prev64, elapsed=elapsed, prev_val=prev64)
        # 32-bit wrap produces much smaller delta than 64-bit wrap
        assert rate32 < rate64


# ---------------------------------------------------------------------------
# map_cpu_memory
# ---------------------------------------------------------------------------

class TestMapCpuMemory:
    def test_all_values_present(self) -> None:
        dev = _dev()
        ts = _ts()
        result = map_cpu_memory(dev, {"cpu_5min": 42.0, "cpu_1min": 38.0, "mem_used_pct": 67.5}, ts)
        types = {r.kpi_type for r in result}
        assert types == {"cpu_5min", "cpu_1min", "mem_used_pct"}

    def test_none_values_skipped(self) -> None:
        result = map_cpu_memory(_dev(), {"cpu_5min": None, "cpu_1min": 30.0, "mem_used_pct": None})
        assert len(result) == 1
        assert result[0].kpi_type == "cpu_1min"

    def test_unit_and_area(self) -> None:
        result = map_cpu_memory(_dev(), {"cpu_5min": 50.0})
        assert result[0].unit == "%"
        assert result[0].kpi_area == "performance"

    def test_timestamp_propagated(self) -> None:
        ts = _ts(3600)
        result = map_cpu_memory(_dev(), {"cpu_5min": 10.0}, ts)
        assert result[0].timestamp == ts


# ---------------------------------------------------------------------------
# map_interfaces
# ---------------------------------------------------------------------------

class TestMapInterfaces:
    def test_no_previous_snapshot_emits_raw(self) -> None:
        dev = _dev()
        ts = _ts()
        interfaces = {1: _make_row(if_index=1, in_octets=5000, out_octets=6000)}
        records, snap = map_interfaces(dev, interfaces, ts, previous_snapshot=None)
        types = {r.kpi_type for r in records}
        assert "if_in_octets_raw" in types
        assert "if_out_octets_raw" in types
        assert "if_oper_status" in types

    def test_with_previous_snapshot_emits_rates(self) -> None:
        dev = _dev()
        t0 = _ts(0)
        t1 = _ts(60)
        prev_snap = {
            1: InterfaceSnapshot(if_index=1, in_octets=1000, out_octets=2000, in_errors=0, timestamp=t0)
        }
        interfaces = {1: _make_row(if_index=1, in_octets=7000, out_octets=8000, in_errors=0)}
        records, new_snap = map_interfaces(dev, interfaces, t1, previous_snapshot=prev_snap)
        types = {r.kpi_type for r in records}
        assert "if_in_octets_rate" in types
        assert "if_out_octets_rate" in types

    def test_rate_calculation_correct(self) -> None:
        dev = _dev()
        t0 = _ts(0)
        t1 = _ts(10)
        prev_snap = {1: InterfaceSnapshot(if_index=1, in_octets=0, out_octets=0, in_errors=0, timestamp=t0)}
        interfaces = {1: _make_row(if_index=1, in_octets=1000, out_octets=2000)}
        records, _ = map_interfaces(dev, interfaces, t1, previous_snapshot=prev_snap)
        in_rate = next(r for r in records if r.kpi_type == "if_in_octets_rate")
        out_rate = next(r for r in records if r.kpi_type == "if_out_octets_rate")
        assert in_rate.value == pytest.approx(100.0)  # 1000 bytes / 10 s
        assert out_rate.value == pytest.approx(200.0)

    def test_counter_wrap_in_rates(self) -> None:
        dev = _dev()
        t0 = _ts(0)
        t1 = _ts(10)
        prev_in = _COUNTER32_MAX - 500
        new_in = 499
        prev_snap = {
            1: InterfaceSnapshot(if_index=1, in_octets=prev_in, out_octets=0, in_errors=0, timestamp=t0)
        }
        interfaces = {1: _make_row(if_index=1, in_octets=new_in, out_octets=1000)}
        records, _ = map_interfaces(dev, interfaces, t1, previous_snapshot=prev_snap)
        in_rate = next(r for r in records if r.kpi_type == "if_in_octets_rate")
        # delta = 500 + 499 + 1 = 1000, rate = 1000/10 = 100.0
        assert in_rate.value == pytest.approx(100.0)

    def test_none_in_octets_skipped(self) -> None:
        dev = _dev()
        t0 = _ts(0)
        t1 = _ts(10)
        prev_snap = {1: InterfaceSnapshot(if_index=1, in_octets=1000, out_octets=None, in_errors=None, timestamp=t0)}
        interfaces = {1: _make_row(if_index=1, in_octets=2000, out_octets=None, in_errors=None)}
        records, _ = map_interfaces(dev, interfaces, t1, previous_snapshot=prev_snap)
        types = [r.kpi_type for r in records]
        assert "if_out_octets_rate" not in types
        assert "if_in_errors_rate" not in types
        assert "if_in_octets_rate" in types

    def test_snapshot_updated(self) -> None:
        dev = _dev()
        ts = _ts()
        interfaces = {2: _make_row(if_index=2, in_octets=300)}
        _, snap = map_interfaces(dev, interfaces, ts, previous_snapshot=None)
        assert 2 in snap
        assert snap[2].in_octets == 300

    def test_oper_status_kpi_area(self) -> None:
        dev = _dev()
        interfaces = {1: _make_row(if_index=1, oper_status=2)}
        records, _ = map_interfaces(dev, interfaces, _ts(), previous_snapshot=None)
        status = next(r for r in records if r.kpi_type == "if_oper_status")
        assert status.kpi_area == "availability"
        assert status.value == pytest.approx(2.0)
