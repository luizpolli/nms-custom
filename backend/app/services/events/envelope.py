"""Canonical internal event envelope for NMS domain events."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(slots=True)
class EventEnvelope:
    """Stable event contract shared by ingestion, alarms, telemetry, and workers."""

    event_type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=_new_id)
    timestamp: str = field(default_factory=_now_iso)
    trace_id: str | None = None
    device_id: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    severity: str | None = None

    def __post_init__(self) -> None:
        self.event_type = str(self.event_type or "unknown")
        self.source = str(self.source or "unknown")
        if self.trace_id is None:
            self.trace_id = self.event_id
        if not isinstance(self.payload, dict):
            self.payload = {"value": self.payload}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventEnvelope:
        return cls(
            event_id=str(data.get("event_id") or _new_id()),
            event_type=str(data.get("event_type") or "unknown"),
            source=str(data.get("source") or "unknown"),
            timestamp=str(data.get("timestamp") or _now_iso()),
            trace_id=data.get("trace_id"),
            device_id=data.get("device_id"),
            object_type=data.get("object_type"),
            object_id=data.get("object_id"),
            severity=data.get("severity"),
            payload=dict(data.get("payload") or {}),
        )
