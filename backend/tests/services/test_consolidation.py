"""Tests for the Cricket-inspired KPI consolidation helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.reports.consolidation import (
    bucketize,
    consolidate,
    floor_bucket,
    percentile,
    split_period,
    summary,
)


def test_percentile_basic() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 50) == pytest.approx(30.0)
    assert percentile(values, 95) == pytest.approx(48.0)
    assert percentile(values, 99) == pytest.approx(49.6)


def test_percentile_empty() -> None:
    assert percentile([], 95) is None


def test_consolidate_functions() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert consolidate(values, "avg") == pytest.approx(2.5)
    assert consolidate(values, "min") == 1.0
    assert consolidate(values, "max") == 4.0
    assert consolidate(values, "sum") == 10.0
    assert consolidate(values, "first") == 1.0
    assert consolidate(values, "last") == 4.0


def test_consolidate_unknown_raises() -> None:
    with pytest.raises(ValueError):
        consolidate([1.0], "wat")  # type: ignore[arg-type]


def test_floor_bucket_aligns_5min() -> None:
    ts = datetime(2026, 5, 16, 14, 37, 12, tzinfo=timezone.utc)
    floored = floor_bucket(ts, "5min")
    assert floored == datetime(2026, 5, 16, 14, 35, 0, tzinfo=timezone.utc)


def test_bucketize_groups_and_consolidates() -> None:
    base = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    samples = [
        (base, 10.0),
        (base + timedelta(seconds=60), 20.0),
        (base + timedelta(seconds=120), 30.0),
        (base + timedelta(minutes=6), 100.0),
    ]
    rolled = bucketize(samples, "5min", "avg")
    assert len(rolled) == 2
    assert rolled[0][0] == base
    assert rolled[0][1] == pytest.approx(20.0)
    assert rolled[1][1] == pytest.approx(100.0)


def test_bucketize_raw_returns_sorted() -> None:
    base = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    samples = [(base + timedelta(seconds=20), 2.0), (base, 1.0)]
    rolled = bucketize(samples, "raw", "avg")
    assert [v for _, v in rolled] == [1.0, 2.0]


def test_summary_returns_full_stats() -> None:
    s = summary([10.0, 20.0, 30.0, 40.0, 50.0])
    assert s["samples"] == 5
    assert s["avg"] == pytest.approx(30.0)
    assert s["min"] == 10.0
    assert s["max"] == 50.0
    assert s["p95"] == pytest.approx(48.0)


def test_summary_handles_empty() -> None:
    s = summary([])
    assert s["samples"] == 0
    assert s["avg"] is None


def test_split_period_divides_evenly() -> None:
    a = datetime(2026, 1, 1, tzinfo=timezone.utc)
    b = a + timedelta(days=8)
    parts = split_period(a, b, 4)
    assert len(parts) == 4
    assert parts[0][1] == a + timedelta(days=2)
    assert parts[-1][1] == b
