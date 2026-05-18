import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[3] / "tools" / "simulators" / "mock_device.py"
spec = importlib.util.spec_from_file_location("mock_device", MODULE_PATH)
mock_device = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mock_device
spec.loader.exec_module(mock_device)


def test_build_syslog_message_contains_cisco_signal():
    device = mock_device.MockDevice(name="r1", ip_address="10.0.0.1")
    msg = mock_device.build_syslog_message(device, 5, alarm=True)
    assert msg.startswith("<131>")
    assert "%LINK-3-UPDOWN" in msg
    assert "r1" in msg


def test_build_gnmi_json_frame_is_line_serializable():
    frame = mock_device.build_gnmi_json_frame("00000000-0000-0000-0000-000000000001", 1)
    raw = json.dumps(frame)
    decoded = json.loads(raw)
    assert decoded["device_id"] == "00000000-0000-0000-0000-000000000001"
    assert len(decoded["updates"]) == 2
    assert decoded["updates"][0]["path"].startswith("/interfaces")


def test_build_snmp_v2c_trap_packet_contains_expected_oids_and_sysname():
    device = mock_device.MockDevice(name="r1", ip_address="10.0.0.1")
    packet = mock_device.build_snmp_v2c_trap_packet(device, 1)

    assert packet.startswith(b"\x30")
    assert b"public" in packet
    assert b"r1" in packet
    assert bytes.fromhex("2b06010201010300") in packet  # sysUpTime.0
    assert bytes.fromhex("2b060106030101040100") in packet  # snmpTrapOID.0
    assert bytes.fromhex("2b0601060301010503") in packet  # linkDown OID value
