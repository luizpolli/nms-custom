"""Unit tests for AlarmCorrelator.classify() — no DB required."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.alarms.correlator import AlarmCorrelator
from app.services.snmp.trap_receiver import TrapEvent

# Trap OID constants (mirrored from correlator for readability)
_LINK_DOWN = "1.3.6.1.6.3.1.1.5.3"
_LINK_UP = "1.3.6.1.6.3.1.1.5.4"
_COLD_START = "1.3.6.1.6.3.1.1.5.1"
_WARM_START = "1.3.6.1.6.3.1.1.5.2"
_AUTH_FAILURE = "1.3.6.1.6.3.1.1.5.5"

_HOST = "10.0.0.1"
_NOW = datetime.now(timezone.utc)


def _event(oid: str, varbinds: dict | None = None) -> TrapEvent:
    return TrapEvent(
        source_host=_HOST,
        source_port=162,
        community="public",
        trap_oid=oid,
        varbinds=varbinds or {},
        received_at=_NOW,
    )


@pytest.fixture()
def correlator() -> AlarmCorrelator:
    # session_factory is never called by classify(); pass None safely
    return AlarmCorrelator(session_factory=None)  # type: ignore[arg-type]


class TestClassifyLinkDown:
    def test_severity_and_category(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(_LINK_DOWN))
        assert result["severity"] == "major"
        assert result["category"] == "link"
        assert result["event_type"] == "linkDown"

    def test_correlation_key_with_if_index(self, correlator: AlarmCorrelator) -> None:
        varbinds = {"1.3.6.1.2.1.2.2.1.1.5": "5"}
        result = correlator.classify(_event(_LINK_DOWN, varbinds))
        assert result["correlation_key"] == f"link:{_HOST}:5"

    def test_correlation_key_unknown_when_no_varbind(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(_LINK_DOWN))
        assert result["correlation_key"] == f"link:{_HOST}:unknown"

    def test_message_contains_host(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(_LINK_DOWN))
        assert _HOST in result["message"]


class TestClassifyLinkUp:
    def test_severity_is_clear(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(_LINK_UP))
        assert result["severity"] == "clear"
        assert result["category"] == "link"
        assert result["event_type"] == "linkUp"

    def test_same_correlation_key_as_link_down(self, correlator: AlarmCorrelator) -> None:
        varbinds = {"1.3.6.1.2.1.2.2.1.1.5": "5"}
        down_key = correlator.classify(_event(_LINK_DOWN, varbinds))["correlation_key"]
        up_key = correlator.classify(_event(_LINK_UP, varbinds))["correlation_key"]
        assert down_key == up_key == f"link:{_HOST}:5"


class TestClassifyColdStart:
    def test_severity_and_category(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(_COLD_START))
        assert result["severity"] == "major"
        assert result["category"] == "device"
        assert result["event_type"] == "coldStart"
        assert result["correlation_key"] == f"device:{_HOST}:reboot"


class TestClassifyWarmStart:
    def test_severity_warning(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(_WARM_START))
        assert result["severity"] == "warning"
        assert result["category"] == "device"
        assert result["event_type"] == "warmStart"


class TestClassifyAuthFailure:
    def test_severity_and_key(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(_AUTH_FAILURE))
        assert result["severity"] == "warning"
        assert result["category"] == "auth"
        assert result["correlation_key"] == f"auth:{_HOST}"


class TestClassifyUnknown:
    def test_unknown_oid_gives_info(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event("1.3.6.1.99.99.99"))
        assert result["severity"] == "info"
        assert result["category"] == "other"

    def test_empty_oid(self, correlator: AlarmCorrelator) -> None:
        result = correlator.classify(_event(""))
        assert result["severity"] == "info"
        assert result["category"] == "other"
