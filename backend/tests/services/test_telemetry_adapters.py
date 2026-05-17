import uuid

import pytest

from app.services.telemetry.adapters import TelemetryAdapterError, parse_gnmi_json_frame


def test_parse_gnmi_json_frame_multiple_updates():
    device_id = uuid.uuid4()
    frame = {
        "device_id": str(device_id),
        "timestamp": 1_700_000_000_000_000_000,
        "labels": {"source": "lab"},
        "updates": [
            {"path": "/interfaces/interface/state/counters/in-octets", "value": {"uintVal": 42}, "unit": "octets"},
            {"path": {"elem": [{"name": "system"}, {"name": "cpu"}]}, "value": 12.5, "quality": "suspect"},
        ],
    }

    samples = parse_gnmi_json_frame(frame)

    assert len(samples) == 2
    assert samples[0].device_id == device_id
    assert samples[0].path.endswith("in-octets")
    assert samples[0].value == 42
    assert samples[0].labels == {"source": "lab"}
    assert samples[1].path == "/system/cpu"
    assert samples[1].quality == "suspect"


def test_parse_decimal_value():
    device_id = uuid.uuid4()
    samples = parse_gnmi_json_frame({"device_id": str(device_id), "path": "/x", "value": {"decimalVal": {"digits": 1234, "precision": 2}}})
    assert samples[0].value == 12.34


def test_parse_rejects_missing_device_id():
    with pytest.raises(TelemetryAdapterError):
        parse_gnmi_json_frame({"path": "/x", "value": 1})
