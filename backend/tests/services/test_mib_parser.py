from __future__ import annotations

from app.services.snmp.mib_parser import parse_mib_text


SAMPLE_MIB = '''
ACME-ALARM-MIB DEFINITIONS ::= BEGIN

acmeAlarmMib MODULE-IDENTITY
    LAST-UPDATED "202605160000Z"
    ORGANIZATION "ACME"
    DESCRIPTION "Example alarm MIB"
    ::= { enterprises 99999 }

acmeLinkFailure NOTIFICATION-TYPE
    OBJECTS { ifIndex, ifDescr, acmeReason }
    STATUS current
    DESCRIPTION "Raised when the ACME device reports a link failure."
    ::= { acmeNotifications 1 }

acmeLinkRecovered NOTIFICATION-TYPE
    OBJECTS { ifIndex, ifDescr }
    STATUS current
    DESCRIPTION "Clears the ACME link failure."
    ::= { acmeNotifications 2 }

END
'''


def test_parse_mib_extracts_module_identity_and_notifications() -> None:
    summary = parse_mib_text(SAMPLE_MIB)

    assert summary.module_name == "ACME-ALARM-MIB"
    assert summary.module_identity_oid == "enterprises 99999"
    assert [n.name for n in summary.notifications] == ["acmeLinkFailure", "acmeLinkRecovered"]
    assert summary.notifications[0].objects == ["ifIndex", "ifDescr", "acmeReason"]
    assert summary.notifications[1].oid == "acmeNotifications 2"
