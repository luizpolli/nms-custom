"""Time-series consolidation helpers.

Cricket-style (Allen, LISA 2000) consolidation functions plus percentiles popularised
by Cisco Prime Performance Manager. Used by KPI reports to roll up raw samples into
fixed buckets and to compute summary statistics for trending/top-N/baseline views.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal

ConsolidationFn = Literal["avg", "min", "max", "last", "first", "sum", "p95", "p99"]
BucketSize = Literal["raw", "5min", "15min", "1h", "1d", "1w"]

BUCKET_SECONDS: dict[BucketSize, int] = {
    "raw": 0,
    "5min": 300,
    "15min": 900,
    "1h": 3600,
    "1d": 86400,
    "1w": 604800,
}


def percentile(values: list[float], pct: float) -> float | None:
    """Linear-interpolation percentile (0-100)."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def consolidate(values: list[float], fn: ConsolidationFn) -> float | None:
    """Apply a consolidation function to a list of samples."""
    if not values:
        return None
    if fn == "avg":
        return sum(values) / len(values)
    if fn == "min":
        return min(values)
    if fn == "max":
        return max(values)
    if fn == "first":
        return values[0]
    if fn == "last":
        return values[-1]
    if fn == "sum":
        return sum(values)
    if fn == "p95":
        return percentile(values, 95)
    if fn == "p99":
        return percentile(values, 99)
    raise ValueError(f"Unknown consolidation function: {fn!r}")


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def floor_bucket(ts: datetime, bucket: BucketSize) -> datetime:
    """Floor a timestamp to its bucket boundary in UTC."""
    if bucket == "raw":
        return _as_utc(ts)
    secs = BUCKET_SECONDS[bucket]
    aware = _as_utc(ts)
    epoch = int(aware.timestamp())
    floored = epoch - (epoch % secs)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def bucketize(
    samples: Iterable[tuple[datetime, float]],
    bucket: BucketSize,
    fn: ConsolidationFn,
) -> list[tuple[datetime, float]]:
    """Group ``samples`` into fixed time buckets and consolidate each bucket.

    Returns a list of ``(bucket_start_utc, value)`` sorted by time.
    For ``bucket == "raw"`` the samples are returned as-is (sorted).
    """
    if bucket == "raw":
        return sorted(((_as_utc(ts), v) for ts, v in samples), key=lambda x: x[0])
    grouped: dict[datetime, list[float]] = defaultdict(list)
    for ts, value in samples:
        grouped[floor_bucket(ts, bucket)].append(value)
    out: list[tuple[datetime, float]] = []
    for ts in sorted(grouped):
        v = consolidate(grouped[ts], fn)
        if v is not None:
            out.append((ts, v))
    return out


def summary(values: list[float]) -> dict[str, float | None]:
    """Cricket-style summary: avg/min/max plus PPM 95th/99th percentile."""
    if not values:
        return {"avg": None, "min": None, "max": None, "p95": None, "p99": None, "samples": 0}
    return {
        "avg": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "samples": len(values),
    }


def split_period(since: datetime, until: datetime, parts: int) -> list[tuple[datetime, datetime]]:
    """Split ``[since, until]`` into ``parts`` equal sub-periods (baselines)."""
    if parts <= 0:
        raise ValueError("parts must be > 0")
    total = (_as_utc(until) - _as_utc(since)).total_seconds()
    step = total / parts
    return [
        (
            _as_utc(since) + timedelta(seconds=step * i),
            _as_utc(since) + timedelta(seconds=step * (i + 1)),
        )
        for i in range(parts)
    ]
