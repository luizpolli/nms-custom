"""Request rate limiting middleware (P0.4).

Design notes
------------
- Sliding-window counter with two backends: Redis (sorted-set ZREMRANGEBYSCORE
  + ZADD + ZCARD in a single pipeline) and an in-process deque-based limiter
  for tests / single-worker deployments.
- Path-based rules: a default bucket for ``/api/*``, a tighter ``sensitive``
  bucket for high-risk routes (auth, commands, credentials, settings/users,
  ai-ops, mibs upload), and an ``anonymous`` bucket for requests that arrive
  without a valid API key.
- Identity key: principal subject when the request carries a known API key,
  otherwise the client IP. This means a single attacker IP can't be hidden
  behind many fresh keys, and a single rotated key can't shadow another.
- Test/dev escape hatches:
    * ``APP_ENV=test`` disables the middleware entirely (suite stays fast and
      hermetic).
    * ``RATE_LIMIT_ENABLED=false`` disables it for any env.
    * Backend ``"auto"`` falls back to memory if Redis is unreachable so a
      Redis outage degrades to in-process limits rather than crashing the API.
- Response shape on block: HTTP 429 with JSON ``{"detail": "..."}`` and the
  three RFC-style headers ``Retry-After``, ``X-RateLimit-Limit``,
  ``X-RateLimit-Remaining``. The first one is what well-behaved clients honor.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.security.auth import configured_api_keys, verify_api_key

# ---------------------------------------------------------------------------
# Rule parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateLimitRule:
    """A ``<count>/<window-seconds>`` rule with a stable name for bookkeeping."""

    name: str
    limit: int
    window_seconds: int

    @classmethod
    def parse(cls, name: str, raw: str) -> RateLimitRule:
        try:
            count_str, window_str = raw.split("/", 1)
            limit = int(count_str.strip())
            window = int(window_str.strip())
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"Invalid rate-limit rule for {name!r}: {raw!r}. "
                "Expected '<count>/<window-seconds>'."
            ) from exc
        if limit <= 0 or window <= 0:
            raise ValueError(
                f"Rate-limit rule for {name!r} must have positive numbers, got {raw!r}."
            )
        return cls(name=name, limit=limit, window_seconds=window)


# Path-prefix rules. Order matters: the first match wins, so the more specific
# prefixes must come first. The middleware always treats POST/PUT/PATCH/DELETE
# on credentials/settings/users as "sensitive" regardless of this map.
_SENSITIVE_PREFIXES: tuple[str, ...] = (
    "/api/commands",
    "/api/command-schedules",
    "/api/credentials",
    "/api/settings/users",
    "/api/settings/roles",
    "/api/settings/api-keys",
    "/api/settings/account-audit",
    "/api/ai-ops",
    "/api/mibs",
)


def _exempt_prefixes() -> tuple[str, ...]:
    raw = settings.rate_limit_exempt_paths or ""
    return tuple(p.strip() for p in raw.split(",") if p.strip())


# ---------------------------------------------------------------------------
# Storage backends
# ---------------------------------------------------------------------------


class _MemoryStore:
    """Per-process sliding window. Safe for tests and single-worker deployments."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def incr(self, key: str, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        async with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            bucket.append(now)
            return len(bucket)

    async def close(self) -> None:
        self._buckets.clear()


class _RedisStore:
    """Redis sliding window backed by sorted sets (ZADD/ZREMRANGEBYSCORE/ZCARD)."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: Any = None
        self._unhealthy_since: float | None = None

    async def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(
            self._redis_url, socket_timeout=2, decode_responses=False
        )
        return self._client

    async def incr(self, key: str, window_seconds: int) -> int:
        client = await self._connect()
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - window_seconds * 1000
        member = f"{now_ms}:{id(object())}"  # unique per call
        async with client.pipeline(transaction=False) as pipe:
            pipe.zremrangebyscore(key, 0, cutoff_ms)
            pipe.zadd(key, {member: now_ms})
            pipe.zcard(key)
            pipe.expire(key, window_seconds + 1)
            results = await pipe.execute()
        # Third pipeline op is ZCARD.
        return int(results[2])

    async def close(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.close()
        except Exception:  # noqa: BLE001 -- best-effort shutdown # nosec B110
            pass
        self._client = None


class _FallbackStore:
    """Tries Redis first; falls back to memory transparently on transport errors.

    A single failed call disables Redis for ``cooldown_seconds`` to avoid
    hammering a flapping host. After the cooldown we try Redis again.
    """

    def __init__(self, redis_url: str, cooldown_seconds: int = 30) -> None:
        self._redis = _RedisStore(redis_url)
        self._memory = _MemoryStore()
        self._cooldown = cooldown_seconds
        self._disabled_until: float = 0.0

    async def incr(self, key: str, window_seconds: int) -> int:
        if time.time() >= self._disabled_until:
            try:
                return await self._redis.incr(key, window_seconds)
            except Exception as exc:  # noqa: BLE001 -- intentional broad fallback
                logger.warning(
                    "rate-limit: redis backend failed, falling back to memory: {}", exc
                )
                self._disabled_until = time.time() + self._cooldown
        return await self._memory.incr(key, window_seconds)

    async def close(self) -> None:
        await self._redis.close()
        await self._memory.close()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware enforcing sliding-window rate limits per identity+rule."""

    def __init__(self, app: ASGIApp, store: Any | None = None) -> None:
        super().__init__(app)
        # Late-parsed so config errors surface at boot, not at first request.
        self._default = RateLimitRule.parse("default", settings.rate_limit_default)
        self._sensitive = RateLimitRule.parse("sensitive", settings.rate_limit_sensitive)
        self._anonymous = RateLimitRule.parse("anonymous", settings.rate_limit_anonymous)
        self._exempt = _exempt_prefixes()
        self._store = store or self._build_store()

    @staticmethod
    def _build_store() -> Any:
        backend = (settings.rate_limit_backend or "auto").lower()
        if backend == "memory":
            return _MemoryStore()
        if backend == "redis":
            return _RedisStore(settings.redis_url)
        return _FallbackStore(settings.redis_url)

    # -- request hooks -----------------------------------------------------

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not self._should_apply(request):
            return await call_next(request)

        rule, identity = self._classify(request)
        key = f"rl:{rule.name}:{identity}"
        try:
            count = await self._store.incr(key, rule.window_seconds)
        except Exception as exc:  # noqa: BLE001 -- never block on limiter errors
            logger.error("rate-limit: store failure, failing open: {}", exc)
            return await call_next(request)

        remaining = max(rule.limit - count, 0)
        if count > rule.limit:
            logger.info(
                "rate-limit: blocked {} (rule={} identity={} count={}/{})",
                request.url.path,
                rule.name,
                identity,
                count,
                rule.limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Rate limit exceeded. Try again later."
                    )
                },
                headers={
                    "Retry-After": str(rule.window_seconds),
                    "X-RateLimit-Limit": str(rule.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Rule": rule.name,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rule.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Rule"] = rule.name
        return response

    # -- classification ----------------------------------------------------

    def _should_apply(self, request: Request) -> bool:
        if not settings.rate_limit_enabled:
            return False
        if (settings.app_env or "").lower() == "test":
            return False
        path = request.url.path
        if any(path == p or path.startswith(p.rstrip("/") + "/") or path == p.rstrip("/")
               for p in self._exempt):
            return False
        # Only rate-limit API surface; static assets and root are out of scope.
        return path.startswith("/api/")

    def _classify(self, request: Request) -> tuple[RateLimitRule, str]:
        path = request.url.path
        method = request.method.upper()

        # Identity: stable per-key bucket when an API key was presented
        # (hashed so we never log raw secrets), otherwise client IP. The
        # hash makes each rotated key its own bucket — an attacker can't
        # dodge limits by spraying many different garbage keys against
        # auth, because each value still gets counted.
        presented = request.headers.get("x-api-key")
        if not presented:
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                presented = auth_header[7:].strip()
        host = request.client.host if request.client else "unknown"
        authenticated = False
        identity = f"ip:{host}"
        if presented:
            # Only treat as authenticated for limiter purposes if the key
            # actually matches a configured one. Otherwise an attacker
            # could rotate garbage values to dodge the IP bucket.
            try:
                allowed = configured_api_keys()
            except Exception:  # noqa: BLE001 -- never block on settings
                allowed = []
            if allowed and verify_api_key(presented, allowed):
                digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()[:16]
                identity = f"key:{digest}"
                authenticated = True

        # Rule selection.
        if any(path.startswith(prefix) for prefix in _SENSITIVE_PREFIXES):
            return self._sensitive, identity
        if not authenticated and method != "GET":
            # Unauth writes are the cheapest abuse vector; use the tight bucket.
            return self._sensitive, identity
        if not authenticated:
            return self._anonymous, identity
        return self._default, identity
