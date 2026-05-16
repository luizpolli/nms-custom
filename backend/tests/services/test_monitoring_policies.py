from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.monitoring_policy import MonitoringPolicy
from app.services.monitoring.policies import DEFAULT_POLICY_SUITE, POLICY_PRESETS, _is_due


def test_policy_presets_include_required_intervals() -> None:
    intervals = {60, 300, 900, 3600, 21600, 43200, 86400}
    suite_intervals = {item[2] for item in DEFAULT_POLICY_SUITE}

    assert intervals <= suite_intervals
    assert any(p['policy_type'] == 'custom_mib' for p in POLICY_PRESETS)
    assert any(p['policy_type'] == 'syslog' for p in POLICY_PRESETS)


def test_policy_due_calculation_with_next_run() -> None:
    now = datetime.now(timezone.utc)
    policy = MonitoringPolicy(
        name='test',
        policy_type='device_health',
        interval_seconds=300,
        next_run_at=now - timedelta(seconds=1),
    )

    assert _is_due(policy, now) is True


def test_policy_not_due_when_last_run_inside_interval() -> None:
    now = datetime.now(timezone.utc)
    policy = MonitoringPolicy(
        name='test',
        policy_type='device_health',
        interval_seconds=300,
        last_run_at=now - timedelta(seconds=60),
    )

    assert _is_due(policy, now) is False
