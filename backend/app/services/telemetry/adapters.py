"""Telemetry protocol adapter helpers.

The runtime receiver can ingest line-delimited JSON that mirrors common gNMI/MDT
update fields. This keeps the protocol boundary testable without requiring lab
devices or generated protobuf stubs in local development.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.telemetry import TelemetrySampleIngest


class TelemetryAdapterError(ValueError):
    """Raised when a telemetry frame cannot be normalized."""


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        # gNMI often emits nanoseconds; accept seconds/ms/ns safely.
        numeric = float(value)
        if numeric > 10_000_000_000_000:
            numeric = numeric / 1_000_000_000
        elif numeric > 10_000_000_000:
            numeric = numeric / 1_000
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TelemetryAdapterError(f"Unsupported timestamp: {value!r}")


def _path_from_update(update: dict[str, Any]) -> str:
    path = update.get("path") or update.get("name")
    if isinstance(path, str):
        return path
    if isinstance(path, dict):
        elems = path.get("elem") or path.get("elements") or []
        names = []
        for elem in elems:
            if isinstance(elem, str):
                names.append(elem)
            elif isinstance(elem, dict):
                names.append(str(elem.get("name") or elem.get("id") or ""))
        joined = "/".join(part for part in names if part)
        return f"/{joined}" if joined else ""
    return ""


def _value_from_update(update: dict[str, Any]) -> float:
    value = update.get("value", update.get("val"))
    if isinstance(value, dict):
        for key in ("doubleVal", "floatVal", "intVal", "uintVal", "decimalVal", "stringVal", "value"):
            if key in value:
                value = value[key]
                if isinstance(value, dict) and "digits" in value:
                    precision = int(value.get("precision", 0) or 0)
                    return float(value["digits"]) / (10**precision)
                break
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise TelemetryAdapterError(f"Telemetry update value is not numeric: {value!r}") from exc


def parse_gnmi_json_frame(frame: str | bytes | dict[str, Any]) -> list[TelemetrySampleIngest]:
    """Parse a JSON gNMI/MDT-like update frame into normalized ingest samples.

    Required frame fields: ``device_id`` plus either a top-level ``updates`` list
    or a single ``path``/``value`` pair. Optional fields include collector_id,
    subscription_id, timestamp, quality, object_type, object_id, labels, unit.
    """
    if isinstance(frame, bytes):
        frame = frame.decode("utf-8")
    payload = json.loads(frame) if isinstance(frame, str) else dict(frame)

    try:
        device_id = uuid.UUID(str(payload["device_id"]))
    except (KeyError, ValueError) as exc:
        raise TelemetryAdapterError("Telemetry frame requires device_id UUID") from exc

    collector_id = uuid.UUID(str(payload["collector_id"])) if payload.get("collector_id") else None
    subscription_id = uuid.UUID(str(payload["subscription_id"])) if payload.get("subscription_id") else None
    timestamp = _parse_timestamp(payload.get("timestamp") or payload.get("ts"))
    base_labels = dict(payload.get("labels") or {})
    updates = payload.get("updates") or [payload]
    samples: list[TelemetrySampleIngest] = []

    for update in updates:
        if not isinstance(update, dict):
            raise TelemetryAdapterError("Telemetry updates must be objects")
        path = _path_from_update(update)
        if not path:
            raise TelemetryAdapterError("Telemetry update requires path")
        labels = {**base_labels, **dict(update.get("labels") or {})}
        samples.append(
            TelemetrySampleIngest(
                collector_id=collector_id,
                subscription_id=subscription_id,
                device_id=device_id,
                path=path,
                value=_value_from_update(update),
                unit=update.get("unit") or payload.get("unit"),
                quality=update.get("quality") or payload.get("quality") or "good",
                object_type=update.get("object_type") or payload.get("object_type") or "device",
                object_id=update.get("object_id") or payload.get("object_id"),
                labels=labels or None,
                raw_payload={"frame": payload, "update": update},
                timestamp=_parse_timestamp(update.get("timestamp") or update.get("ts") or timestamp),
            )
        )
    return samples
