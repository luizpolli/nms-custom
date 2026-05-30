"""Best-effort worker heartbeats via Redis.

Each worker loop publishes a small status record to Redis so the API can
report which workers are alive, when they last ran, and whether they are
currently failing. All Redis calls are wrapped in try/except — heartbeat
failures must never break the worker.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger

WORKER_KINDS: tuple[str, ...] = (
    "monitoring-policies",
    "topology",
    "trap-receiver",
    "syslog-receiver",
    "report-scheduler",
    "telemetry-receiver",
    "worker-alarm",
    "worker-discovery",
    "worker-telemetry",
)

_KEY_PREFIX = "nms:workers:"


def _key(kind: str) -> str:
    return f"{_KEY_PREFIX}{kind}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class WorkerStatus:
    """Aggregated view of one worker's last-known state."""

    kind: str
    last_run_at: str | None = None
    last_status: str | None = None  # "ok" | "error" | "starting"
    runs_total: int = 0
    errors_total: int = 0
    last_error: str | None = None
    expected_interval_s: int | None = None
    is_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkerHeartbeat:
    """Per-worker heartbeat publisher backed by Redis (best-effort)."""

    def __init__(self, kind: str, expected_interval_s: int | None = None) -> None:
        self.kind = kind
        self.expected_interval_s = expected_interval_s
        self._redis: Any = None

    async def _client(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis

            from app.config import settings

            self._redis = aioredis.from_url(
                settings.redis_url, socket_timeout=2, decode_responses=True
            )
        except Exception as exc:
            logger.debug("Heartbeat redis unavailable for {}: {}", self.kind, exc)
            self._redis = None
        return self._redis

    async def _hset(self, mapping: dict[str, Any]) -> None:
        client = await self._client()
        if client is None:
            return
        try:
            await client.hset(_key(self.kind), mapping=mapping)
            # Expire long enough that a brief outage doesn't drop the record,
            # short enough that a removed worker eventually disappears.
            await client.expire(_key(self.kind), 3600)
        except Exception as exc:
            logger.debug("Heartbeat hset failed for {}: {}", self.kind, exc)

    async def _hincrby(self, field: str, amount: int = 1) -> None:
        client = await self._client()
        if client is None:
            return
        try:
            await client.hincrby(_key(self.kind), field, amount)
        except Exception as exc:
            logger.debug("Heartbeat hincrby failed for {}: {}", self.kind, exc)

    async def starting(self) -> None:
        await self._hset(
            {
                "kind": self.kind,
                "last_status": "starting",
                "last_run_at": _now_iso(),
                "expected_interval_s": str(self.expected_interval_s or ""),
            }
        )

    async def success(self) -> None:
        await self._hset(
            {
                "kind": self.kind,
                "last_status": "ok",
                "last_run_at": _now_iso(),
                "last_error": "",
                "expected_interval_s": str(self.expected_interval_s or ""),
            }
        )
        await self._hincrby("runs_total", 1)

    async def failure(self, error: str) -> None:
        await self._hset(
            {
                "kind": self.kind,
                "last_status": "error",
                "last_run_at": _now_iso(),
                "last_error": error[:500],
                "expected_interval_s": str(self.expected_interval_s or ""),
            }
        )
        await self._hincrby("errors_total", 1)

    async def close(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        except Exception as exc:
            logger.debug("Heartbeat redis close failed for {}: {}", self.kind, exc)
        self._redis = None


def _parse_status(kind: str, raw: dict[str, str] | None) -> WorkerStatus:
    raw = raw or {}
    last_run_at = raw.get("last_run_at") or None
    expected = raw.get("expected_interval_s")
    expected_i = int(expected) if expected and expected.isdigit() else None

    is_stale = False
    if last_run_at and expected_i:
        try:
            ts = datetime.fromisoformat(last_run_at)
            age_s = (datetime.now(UTC) - ts).total_seconds()
            is_stale = age_s > expected_i * 3
        except ValueError:
            is_stale = False
    elif not last_run_at:
        is_stale = True

    return WorkerStatus(
        kind=kind,
        last_run_at=last_run_at,
        last_status=raw.get("last_status") or None,
        runs_total=int(raw.get("runs_total") or 0),
        errors_total=int(raw.get("errors_total") or 0),
        last_error=raw.get("last_error") or None,
        expected_interval_s=expected_i,
        is_stale=is_stale,
    )


async def get_all_worker_status(kinds: Iterable[str] = WORKER_KINDS) -> list[WorkerStatus]:
    """Fetch heartbeat status for every known worker. Best-effort."""
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        client = aioredis.from_url(settings.redis_url, socket_timeout=2, decode_responses=True)
    except Exception as exc:
        logger.debug("get_all_worker_status: redis unavailable: {}", exc)
        return [WorkerStatus(kind=k, is_stale=True) for k in kinds]

    out: list[WorkerStatus] = []
    try:
        for kind in kinds:
            try:
                raw = await client.hgetall(_key(kind))
            except Exception:
                raw = None
            out.append(_parse_status(kind, raw))
    finally:
        try:
            await client.aclose()
        except Exception as exc:
            logger.debug("get_all_worker_status: redis close failed: {}", exc)
    return out
