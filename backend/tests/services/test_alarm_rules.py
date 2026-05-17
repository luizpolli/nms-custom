from __future__ import annotations

from types import SimpleNamespace

from app.services.alarms.rules import AlarmRuleContext, apply_rule, normalize_alarm_severity


def _rule(**overrides):
    data = {
        "id": "rule-1",
        "name": "Customer severity override",
        "source_type": "event",
        "match_field": "event_type",
        "match_operator": "equals",
        "match_pattern": "custom.cpu.high",
        "severity": "critical",
        "category": None,
        "event_type": None,
        "message_template": None,
        "correlation_key_template": None,
        "auto_clear": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _ctx(**overrides):
    data = {
        "source_type": "event",
        "source_host": "router-1",
        "trap_oid": None,
        "event_type": "custom.cpu.high",
        "category": "custom",
        "message": "CPU is high",
        "severity": "warning",
        "varbinds": {"cpu": "96"},
        "correlation_key": "event:router-1:custom.cpu.high",
    }
    data.update(overrides)
    return AlarmRuleContext(**data)


def test_apply_rule_overrides_custom_event_severity() -> None:
    cls = {
        "severity": "warning",
        "category": "custom",
        "event_type": "custom.cpu.high",
        "message": "CPU is high",
        "correlation_key": "event:router-1:custom.cpu.high",
    }

    result = apply_rule(cls, _rule(severity="major"), _ctx())

    assert result["severity"] == "major"
    assert result["auto_clear"] is False
    assert result["matched_rule_name"] == "Customer severity override"


def test_apply_rule_autoclear_marks_matching_event_as_clear() -> None:
    cls = {
        "severity": "critical",
        "category": "custom",
        "event_type": "custom.cpu.high",
        "message": "CPU is high",
        "correlation_key": "event:router-1:custom.cpu.high",
    }

    result = apply_rule(cls, _rule(auto_clear=True, severity="critical"), _ctx())

    assert result["severity"] == "clear"
    assert result["auto_clear"] is True
    assert result["correlation_key"] == "event:router-1:custom.cpu.high"


def test_normalize_syslog_and_itu_severity_values() -> None:
    assert normalize_alarm_severity("err") == "major"
    assert normalize_alarm_severity("2") == "critical"
    assert normalize_alarm_severity("notice") == "info"
    assert normalize_alarm_severity("cleared") == "clear"


def test_apply_rule_templates_message_and_correlation_key() -> None:
    cls = {
        "severity": "warning",
        "category": "custom",
        "event_type": "custom.cpu.high",
        "message": "CPU is high",
        "correlation_key": "event:router-1:custom.cpu.high",
    }

    result = apply_rule(
        cls,
        _rule(
            source_type="any",
            message_template="{source_host} CPU at {varbind_cpu}%",
            correlation_key_template="cpu:{source_host}",
        ),
        _ctx(),
    )

    assert result["message"] == "router-1 CPU at 96%"
    assert result["correlation_key"] == "cpu:router-1"
