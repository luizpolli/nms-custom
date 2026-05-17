"""Tests for telemetry sample normalization."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.telemetry import TelemetrySensorPath
from app.schemas.telemetry import TelemetrySampleIngest
from app.services.telemetry import normalize_sample_to_kpi


def test_normalize_sample_uses_sensor_catalog_mapping():
    device_id = uuid.uuid4()
    sample = TelemetrySampleIngest(
        device_id=device_id,
        path="/interfaces/interface/state/counters/in-octets",
        value=123.0,
        unit="bytes",
        object_type="interface",
        object_id="GigabitEthernet0/0",
        labels={"direction": "in"},
        timestamp=datetime(2026, 5, 17, tzinfo=timezone.utc),
    )
    sensor = TelemetrySensorPath(
        path=sample.path,
        metric_name="interface.in_octets",
        kpi_type="if_in_octets",
        unit="octets",
        object_type="interface",
        labels={"vendor": "cisco"},
    )

    kpi = normalize_sample_to_kpi(sample, sensor)

    assert kpi.device_id == device_id
    assert kpi.source_type == "telemetry"
    assert kpi.technology == "telemetry"
    assert kpi.kpi_area == "telemetry"
    assert kpi.metric_name == "interface.in_octets"
    assert kpi.kpi_type == "if_in_octets"
    assert kpi.unit == "bytes"
    assert kpi.object_type == "interface"
    assert kpi.object_id == "GigabitEthernet0/0"
    assert kpi.labels == {"vendor": "cisco", "direction": "in"}
    assert kpi.meta["path"] == sample.path


def test_normalize_sample_falls_back_to_path_metric():
    sample = TelemetrySampleIngest(
        device_id=uuid.uuid4(),
        path="/components/component/state/temperature/instant",
        value=42.5,
    )

    kpi = normalize_sample_to_kpi(sample)

    assert kpi.metric_name == "components.component.state.temperature.instant"
    assert kpi.kpi_type == "components.component.state.temperature.instant"[:50]
    assert kpi.object_type == "device"
    assert kpi.quality == "good"

from app.services.telemetry.receiver import TelemetryReceiverConfig


def test_telemetry_receiver_config_defaults():
    cfg = TelemetryReceiverConfig()
    assert cfg.transport == "gnmi"
    assert cfg.bind_port == 57400
    assert cfg.idle_heartbeat_seconds == 30
