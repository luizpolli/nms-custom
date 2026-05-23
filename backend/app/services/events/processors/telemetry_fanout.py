"""Telemetry fan-out rules processor.

Applies a configurable in-memory ruleset to normalized telemetry events and
routes each matching event to one or more destinations:
  - KPI updates (existing KPIThresholdEvaluator path)
  - Alerting thresholds (same path — evaluator already handles this)
  - Downstream subscribers (optional webhook/event re-publication via the bus)

Rules are loaded from a list of FanoutRule objects at construction time.
Rule matching is intentionally lean: severity prefix, kpi_type glob, device tag set.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger

from app.services.events.envelope import EventEnvelope

SessionFactory = Callable[[], Any]


@dataclass(slots=True)
class FanoutRule:
    """A single fan-out routing rule."""

    name: str
    # Matched by fnmatch against event.event_type (e.g. "telemetry.*")
    event_type_pattern: str = "*"
    # Matched against event.severity (empty = any)
    severity: str = ""
    # Matched against payload["kpi_type"] (empty = any)
    kpi_type: str = ""
    # All tags must be present in payload["device_tags"] list
    required_device_tags: list[str] = field(default_factory=list)
    # Where to route: "kpi" | "threshold" | "webhook".
    # "threshold" runs the KPI evaluator and emits telemetry.kpi.evaluated.
    destinations: list[str] = field(default_factory=lambda: ["threshold"])
    # Webhook URL when destinations includes "webhook"
    webhook_url: str = ""


def _rule_matches(rule: FanoutRule, event: EventEnvelope) -> bool:
    if not fnmatch.fnmatch(event.event_type or "", rule.event_type_pattern):
        return False
    if rule.severity and (event.severity or "") != rule.severity:
        return False
    payload = event.payload or {}
    if rule.kpi_type and payload.get("kpi_type") != rule.kpi_type:
        return False
    if rule.required_device_tags:
        device_tags = set(payload.get("device_tags") or [])
        if not set(rule.required_device_tags).issubset(device_tags):
            return False
    return True


class TelemetryFanoutProcessor:
    """Apply fan-out rules to a normalized telemetry event."""

    def __init__(
        self,
        session_factory: SessionFactory,
        rules: list[FanoutRule] | None = None,
        bus: Any = None,
    ) -> None:
        self._sf = session_factory
        self.rules: list[FanoutRule] = rules if rules is not None else [_default_rule()]
        self._bus = bus

    async def process(self, event: EventEnvelope) -> dict[str, int]:
        """Apply all matching rules. Returns dict of destination -> count routed."""
        routed: dict[str, int] = {}
        for rule in self.rules:
            if not _rule_matches(rule, event):
                continue
            logger.debug("FanoutRule '{}' matched event_id={}", rule.name, event.event_id)
            for dest in rule.destinations:
                n = await self._route(dest, event, rule)
                routed[dest] = routed.get(dest, 0) + n
        return routed

    async def _route(self, dest: str, event: EventEnvelope, rule: FanoutRule) -> int:
        if dest == "kpi":
            return await self._route_kpi(event, publish_evaluated=False)
        if dest == "threshold":
            return await self._route_kpi(event, publish_evaluated=True)
        if dest == "webhook":
            return await self._route_webhook(event, rule.webhook_url)
        logger.debug("FanoutProcessor: unknown destination '{}' — skipping", dest)
        return 0

    async def _route_kpi(self, event: EventEnvelope, *, publish_evaluated: bool) -> int:
        kpi_id = event.payload.get("kpi_id")
        if kpi_id is None:
            return 0
        try:
            kpi_id_int = int(kpi_id)
        except (TypeError, ValueError):
            logger.debug("FanoutProcessor: non-integer kpi_id={} — skipping", kpi_id)
            return 0
        from app.models.kpi import KPI
        from app.services.kpi.thresholds import KPIThresholdEvaluator

        async with self._sf() as session:
            kpi = await session.get(KPI, kpi_id_int)
        if kpi is None:
            return 0
        evaluator = KPIThresholdEvaluator(self._sf)
        count = await evaluator.evaluate([kpi])
        if publish_evaluated:
            await self._publish_kpi_evaluated(event, kpi_id_int, count)
        return count

    async def _publish_kpi_evaluated(self, event: EventEnvelope, kpi_id: int, tca_count: int) -> None:
        if self._bus is None:
            return
        severity = "nominal" if tca_count == 0 else "warning"
        fan_out = EventEnvelope(
            event_type="telemetry.kpi.evaluated",
            source="fanout-processor",
            device_id=event.device_id or str(event.payload.get("device_id") or ""),
            trace_id=event.trace_id,
            severity=severity,
            payload={
                "kpi_id": kpi_id,
                "device_id": event.device_id or str(event.payload.get("device_id") or ""),
                "value": event.payload.get("value"),
                "severity": severity,
            },
        )
        await self._bus.publish(fan_out)

    async def _route_webhook(self, event: EventEnvelope, url: str) -> int:
        if not url or self._bus is None:
            return 0
        republish = EventEnvelope(
            event_type="telemetry.fanout.republish",
            source="fanout-processor",
            device_id=event.device_id,
            trace_id=event.trace_id,
            severity=event.severity,
            payload={**event.payload, "webhook_url": url},
        )
        await self._bus.publish(republish)
        return 1


def _default_rule() -> FanoutRule:
    return FanoutRule(
        name="default",
        event_type_pattern="telemetry.*",
        destinations=["threshold"],
    )
