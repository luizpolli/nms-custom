"""UDP/socket-level receiver integration tests.

These tests exercise the actual datagram listener paths instead of calling
parsers or correlators directly. SNMP trap socket coverage is guarded because
some local dev environments intentionally omit pysnmp-lextudio.
"""

from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path

import pytest

from app.services.syslog.receiver import SyslogEvent, SyslogReceiver


_TOOLS_ROOT = Path(__file__).resolve().parents[3] / "tools" / "simulators"
if str(_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOLS_ROOT))


def _free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class _UdpClient(asyncio.DatagramProtocol):
    pass


async def _send_udp(payload: bytes, host: str, port: int) -> None:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        _UdpClient,
        remote_addr=(host, port),
    )
    try:
        transport.sendto(payload)
        await asyncio.sleep(0)
    finally:
        transport.close()


@pytest.mark.integration
async def test_syslog_receiver_dispatches_udp_datagram_over_socket() -> None:
    received: asyncio.Queue[SyslogEvent] = asyncio.Queue()
    port = _free_udp_port()
    receiver = SyslogReceiver(bind_host="127.0.0.1", bind_port=port)

    async def _handler(event: SyslogEvent) -> None:
        await received.put(event)

    receiver.on_syslog(_handler)
    await receiver.start()
    try:
        await _send_udp(
            b"<131>May 23 router-socket-1 %LINK-3-UPDOWN: Interface Gig0/1 down",
            "127.0.0.1",
            port,
        )
        event = await asyncio.wait_for(received.get(), timeout=2)
    finally:
        await receiver.stop()

    assert event.source_host == "127.0.0.1"
    assert event.facility == 16
    assert event.severity == "error"
    assert event.hostname == "router-socket-1"
    assert "%LINK-3-UPDOWN" in event.message


@pytest.mark.integration
async def test_syslog_receiver_dispatches_malformed_udp_payload_as_info() -> None:
    received: asyncio.Queue[SyslogEvent] = asyncio.Queue()
    port = _free_udp_port()
    receiver = SyslogReceiver(bind_host="127.0.0.1", bind_port=port)
    receiver.on_syslog(received.put_nowait)

    await receiver.start()
    try:
        await _send_udp(b"\x00not-a-priority syslog payload\r\n", "127.0.0.1", port)
        event = await asyncio.wait_for(received.get(), timeout=2)
    finally:
        await receiver.stop()

    assert event.source_host == "127.0.0.1"
    assert event.facility is None
    assert event.severity == "info"
    assert event.hostname is None
    assert event.message == "not-a-priority syslog payload"


@pytest.mark.integration
async def test_trap_receiver_dispatches_raw_snmpv2c_trap_over_socket() -> None:
    from app.services.snmp import trap_receiver

    if trap_receiver.engine is None:
        pytest.skip("pysnmp-lextudio is not installed in this environment")

    from app.services.snmp.trap_receiver import SNMPTrapReceiver, TrapEvent
    from mock_device import MockDevice, build_snmp_v2c_trap_packet  # type: ignore[import-not-found]

    received: asyncio.Queue[TrapEvent] = asyncio.Queue()
    port = _free_udp_port()
    receiver = SNMPTrapReceiver(bind_host="127.0.0.1", bind_port=port, communities=["public"])
    receiver.on_trap(received.put_nowait)

    packet = build_snmp_v2c_trap_packet(
        MockDevice(name="router-trap-socket-1", ip_address="10.255.0.21"),
        sequence=1,
        community="public",
        trap_type="link-down",
    )

    await receiver.start()
    try:
        await _send_udp(packet, "127.0.0.1", port)
        event = await asyncio.wait_for(received.get(), timeout=2)
    finally:
        await receiver.stop()

    assert event.source_host in ("127.0.0.1", "?")
    assert event.source_port >= 0
    assert event.trap_oid == "1.3.6.1.6.3.1.1.5.3"
    assert event.varbinds["1.3.6.1.2.1.1.5.0"] == "router-trap-socket-1"
    assert event.varbinds["1.3.6.1.6.3.1.1.4.1.0"] == event.trap_oid


@pytest.mark.integration
async def test_trap_receiver_accepts_snmpv3_authpriv_trap_over_socket() -> None:
    from app.services.snmp import trap_receiver

    if trap_receiver.engine is None:
        pytest.skip("pysnmp-lextudio is not installed in this environment")

    from pysnmp.hlapi.v3arch.asyncio import (
        ContextData,
        NotificationType,
        ObjectIdentity,
        SnmpEngine,
        UdpTransportTarget,
        UsmUserData,
        send_notification,
        usmAesCfb128Protocol,
        usmHMAC192SHA256AuthProtocol,
    )
    from pysnmp.proto.rfc1902 import OctetString

    from app.services.snmp.trap_receiver import SNMPTrapReceiver, TrapEvent, TrapV3User

    engine_id = "8000000001020304"
    received: asyncio.Queue[TrapEvent] = asyncio.Queue()
    port = _free_udp_port()
    receiver = SNMPTrapReceiver(
        bind_host="127.0.0.1",
        bind_port=port,
        v3_users=[
            TrapV3User(
                user="nms-trap",
                auth_protocol="SHA256",
                auth_key="authpass123",
                priv_protocol="AES128",
                priv_key="privpass123",
                engine_id=engine_id,
            )
        ],
    )
    receiver.on_trap(received.put_nowait)

    await receiver.start()
    sender = SnmpEngine(OctetString(hexValue=engine_id))
    try:
        # v3 TRAP PDUs are authoritative on the sender side, so the sender
        # engine must carry the engineID the receiver has the user keyed to.
        error_indication, _, _, _ = await send_notification(
            sender,
            UsmUserData(
                "nms-trap",
                "authpass123",
                "privpass123",
                authProtocol=usmHMAC192SHA256AuthProtocol,
                privProtocol=usmAesCfb128Protocol,
            ),
            await UdpTransportTarget.create(("127.0.0.1", port)),
            ContextData(),
            "trap",
            NotificationType(ObjectIdentity("1.3.6.1.6.3.1.1.5.3")),
        )
        assert error_indication is None
        event = await asyncio.wait_for(received.get(), timeout=5)
    finally:
        sender.transportDispatcher.closeDispatcher()
        await receiver.stop()

    assert event.trap_oid == "1.3.6.1.6.3.1.1.5.3"
