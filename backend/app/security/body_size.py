"""Request body-size limit middleware (P2).

Design notes
------------
- A single Starlette ``BaseHTTPMiddleware`` that enforces a configurable
  maximum request body size for all ``/api/*`` routes.
- Per-route overrides allow tighter caps on bulk endpoints and a generous cap
  for MIB uploads (which are the only paths that intentionally receive large
  payloads).
- When the ``Content-Length`` header is present and already exceeds the limit
  the request is rejected immediately with HTTP 413 before the body is read,
  avoiding unnecessary I/O.
- When the body arrives without a ``Content-Length`` (chunked transfer) the
  middleware reads the stream and rejects if total bytes exceed the limit.
- The middleware is skipped in ``APP_ENV=test`` (consistent with
  ``RateLimitMiddleware``) and when ``BODY_SIZE_LIMIT_ENABLED=false``.

Configurable settings (all via env / .env.example):

    BODY_SIZE_LIMIT_ENABLED   true (default)
    MAX_REQUEST_BODY_MB       1   — default cap for ordinary API requests
    MAX_BULK_REQUEST_BODY_MB  4   — cap for bulk endpoints (e.g. bulk alarm ops)
    MAX_MIB_UPLOAD_BODY_MB    10  — cap for MIB file uploads (overrides MIB_UPLOAD_MAX_BYTES too)

Route classification (first match):
    /api/mibs/upload          → MAX_MIB_UPLOAD_BODY_MB
    /api/alarms/bulk-*        → MAX_BULK_REQUEST_BODY_MB
    /api/devices  (POST/PUT)  → MAX_BULK_REQUEST_BODY_MB  (import CSV / bulk add)
    /api/telemetry/*          → MAX_BULK_REQUEST_BODY_MB
    everything else /api/*    → MAX_REQUEST_BODY_MB

GET, HEAD, OPTIONS, DELETE requests without a body are always exempt.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

# Methods that may carry a meaningful body.
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

# Routes classified as "bulk" receive the larger cap.
_BULK_PREFIXES: tuple[str, ...] = (
    "/api/alarms/bulk",
    "/api/alarms/",  # bulk ack / resolve POSTs
    "/api/devices",
    "/api/telemetry",
)

# MIB upload route receives its own (largest) cap.
_MIB_UPLOAD_PATH = "/api/mibs/upload"


def _mb(mb: int | float) -> int:
    return int(mb * 1024 * 1024)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-route maximum request body sizes."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._default = _mb(settings.max_request_body_mb)
        self._bulk = _mb(settings.max_bulk_request_body_mb)
        self._mib = _mb(settings.max_mib_upload_body_mb)

    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next: Callable):  # type: ignore[override]
        if not self._should_apply(request):
            return await call_next(request)

        limit = self._limit_for(request)

        # Fast-path: reject based on Content-Length header alone.
        cl_header = request.headers.get("content-length")
        if cl_header:
            try:
                cl = int(cl_header)
            except ValueError:
                cl = 0
            if cl > limit:
                return self._reject(request, limit, declared=cl)

        # Slow-path for chunked / unknown Content-Length: read and buffer.
        body_chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                logger.warning(
                    "body-size: rejected {} {} (read {} bytes, limit {} bytes)",
                    request.method,
                    request.url.path,
                    total,
                    limit,
                )
                return self._reject(request, limit, declared=None)
            body_chunks.append(chunk)

        # Rebind the already-consumed stream so route handlers can re-read it.
        body = b"".join(body_chunks)

        async def _body_override() -> bytes:
            return body

        request._body = body  # type: ignore[attr-defined]  # Starlette internal

        return await call_next(request)

    # ------------------------------------------------------------------

    @staticmethod
    def _should_apply(request: Request) -> bool:
        if not settings.body_size_limit_enabled:
            return False
        if (settings.app_env or "").lower() == "test":
            return False
        if request.method not in _BODY_METHODS:
            return False
        return request.url.path.startswith("/api/")

    def _limit_for(self, request: Request) -> int:
        path = request.url.path
        if path.startswith(_MIB_UPLOAD_PATH):
            return self._mib
        if any(path.startswith(p) for p in _BULK_PREFIXES):
            return self._bulk
        return self._default

    @staticmethod
    def _reject(request: Request, limit: int, declared: int | None) -> JSONResponse:
        detail = (
            f"Request body too large. Maximum allowed: {limit // (1024 * 1024)} MB "
            f"for this endpoint."
        )
        if declared is not None:
            detail += f" Declared Content-Length was {declared} bytes."
        logger.info(
            "body-size: rejected {} {} limit={} declared={}",
            request.method,
            request.url.path,
            limit,
            declared,
        )
        return JSONResponse(
            status_code=413,
            content={"detail": detail},
            headers={"X-Max-Body-Bytes": str(limit)},
        )
