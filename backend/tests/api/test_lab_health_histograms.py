"""Lab health histogram helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.lab import _eps_histogram, _histogram_bucket_seconds, _latency_histogram


def test_histogram_bucket_seconds_keeps_short_windows_granular() -> None:
    assert _histogram_bucket_seconds(15) == 60
    assert _histogram_bucket_seconds(120) == 300
    assert _histogram_bucket_seconds(1440) == 3600


def test_eps_histogram_counts_samples_per_bucket() -> None:
    since = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    now = since + timedelta(minutes=3)
    timestamps = [
        since + timedelta(seconds=1),
        since + timedelta(seconds=59),
        since + timedelta(seconds=60),
        (since + timedelta(seconds=179)).replace(tzinfo=None),
    ]

    buckets = _eps_histogram(timestamps, since, now, bucket_seconds=60)

    assert [bucket["count"] for bucket in buckets] == [2, 1, 1]
    assert [bucket["eps"] for bucket in buckets] == [0.03, 0.02, 0.02]


def test_eps_histogram_ignores_out_of_window_samples_and_clamps_now() -> None:
    since = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    now = since + timedelta(seconds=90)
    timestamps = [
        since - timedelta(seconds=1),
        since,
        since + timedelta(seconds=75),
        now,
        now + timedelta(seconds=1),
    ]

    buckets = _eps_histogram(timestamps, since, now, bucket_seconds=60)

    assert [bucket["count"] for bucket in buckets] == [1, 2]
    assert buckets[-1]["end"] == now.isoformat()
    assert buckets[-1]["eps"] == 0.07


def test_latency_histogram_is_honest_when_empty() -> None:
    histogram = _latency_histogram([])

    assert histogram["sample_count"] == 0
    assert histogram["note"]
    assert sum(bucket["count"] for bucket in histogram["buckets"]) == 0


def test_latency_histogram_buckets_ms_values() -> None:
    histogram = _latency_histogram([5, 10, 50, 100, 250, 1000])

    assert histogram["sample_count"] == 6
    assert [bucket["count"] for bucket in histogram["buckets"]] == [1, 1, 1, 1, 1, 1]
    assert histogram["note"] is None
