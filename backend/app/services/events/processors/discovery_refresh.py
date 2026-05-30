"""Discovery refresh orchestrator.

Subscribes to inventory-change and device-config events and triggers targeted
(per-device) refresh with:
  - Per-device debounce window (default 60 s; configurable via debounce_s)
  - Global rate-limit: max N refreshes per minute (configurable via max_per_minute)
  - Skip if a refresh is already in-flight for that device

Uses DiscoveryEngine.persist() as the targeted refresh entry point; does NOT
reimplement discovery logic.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from typing import Any

from loguru import logger

SessionFactory = Callable[[], Any]

_DEFAULT_DEBOUNCE_S = 60.0
_DEFAULT_MAX_PER_MINUTE = 20


class DiscoveryRefreshOrchestrator:
    """Rate-limited, debounced, in-flight-aware discovery refresh trigger."""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        debounce_s: float = _DEFAULT_DEBOUNCE_S,
        max_per_minute: int = _DEFAULT_MAX_PER_MINUTE,
    ) -> None:
        self._sf = session_factory
        self.debounce_s = debounce_s
        self.max_per_minute = max_per_minute
        # device_id str -> monotonic timestamp of last scheduled refresh
        self._last_scheduled: dict[str, float] = {}
        # device_ids currently in-flight
        self._in_flight: set[str] = set()
        # sliding window of refresh timestamps (last 60 s)
        self._window: deque[float] = deque()

    def should_refresh(self, device_id: str) -> tuple[bool, str]:
        """Return (should, reason) — pure check, no side-effects."""
        if not device_id:
            return False, "no_device_id"

        if device_id in self._in_flight:
            return False, "in_flight"

        now = time.monotonic()
        last = self._last_scheduled.get(device_id)
        if last is not None and (now - last) < self.debounce_s:
            return False, "debounced"

        self._prune_window(now)
        if len(self._window) >= self.max_per_minute:
            return False, "rate_limited"

        return True, "ok"

    async def maybe_refresh(self, device_id: str, *, reason: str = "") -> bool:
        """Schedule a targeted refresh if debounce/rate limits allow.

        Returns True when refresh was triggered.
        """
        ok, skip_reason = self.should_refresh(device_id)
        if not ok:
            logger.debug(
                "DiscoveryRefresh skipped device={} reason={}", device_id, skip_reason
            )
            return False

        self._record_scheduled(device_id)
        self._in_flight.add(device_id)
        logger.debug("DiscoveryRefresh triggered device={} reason={}", device_id, reason)
        try:
            await self._run_refresh(device_id)
        except Exception as exc:
            logger.warning("DiscoveryRefresh failed device={}: {}", device_id, exc)
        finally:
            self._in_flight.discard(device_id)
        return True

    async def _run_refresh(self, device_id: str) -> None:
        """Perform targeted refresh — re-fingerprints via SNMP and persists.

        Skeletons when no SNMP credentials are available; this is expected in
        test/simulation environments where SNMPEngine is not wired.
        """

        from app.models.device import Device

        async with self._sf() as session:
            try:
                import uuid as _uuid
                device = await session.get(Device, _uuid.UUID(device_id))
            except (ValueError, Exception):
                device = None

        if device is None:
            logger.debug("DiscoveryRefresh: device {} not found — skipping", device_id)
            return

        try:
            from app.services.discovery.engine import DiscoveryEngine
            from app.services.snmp.engine import SNMPEngine

            engine = DiscoveryEngine(SNMPEngine(), self._sf)  # type: ignore[arg-type]
            discovered = await engine.scan_subnet(device.ip_address + "/32", ["public"])
            if discovered:
                await engine.persist(discovered)
                logger.info("DiscoveryRefresh: persisted {} for device {}", len(discovered), device_id)
        except Exception as exc:
            logger.debug("DiscoveryRefresh: scan skipped for device {}: {}", device_id, exc)

    def _prune_window(self, now: float) -> None:
        cutoff = now - 60.0
        while self._window and self._window[0] < cutoff:
            self._window.popleft()

    def _record_scheduled(self, device_id: str) -> None:
        now = time.monotonic()
        self._last_scheduled[device_id] = now
        self._prune_window(now)
        self._window.append(now)
