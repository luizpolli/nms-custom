from __future__ import annotations

from app.services.syslog.receiver import parse_syslog


def test_parse_rfc5424_syslog() -> None:
    event = parse_syslog(
        b'<134>1 2026-05-16T20:00:00Z router-1 IOS-XR - LINK-3-UPDOWN [meta sequenceId="1"] Interface down',
        '10.0.0.1',
        514,
    )

    assert event.source_host == '10.0.0.1'
    assert event.facility == 16
    assert event.severity == 'info'
    assert event.app_name == 'IOS-XR'
    assert event.msg_id == 'LINK-3-UPDOWN'
    assert event.message == 'Interface down'


def test_parse_bsd_syslog_priority() -> None:
    event = parse_syslog(b'<131>May 16 router-1 %LINK-3-UPDOWN: Interface down', '10.0.0.1', 514)

    assert event.facility == 16
    assert event.severity == 'error'
    assert '%LINK-3-UPDOWN' in event.message
