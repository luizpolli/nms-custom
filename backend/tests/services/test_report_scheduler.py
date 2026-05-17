"""Tests for the report scheduler cadence and param materialization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.report_schedule import ReportSchedule
from app.services.reports.scheduler import (
    cadence_delta,
    is_due,
    materialize_params,
)


def test_cadence_delta_known_value() -> None:
    assert cadence_delta("every_5m") == timedelta(minutes=5)
    assert cadence_delta("daily") == timedelta(days=1)
    assert cadence_delta("weekly") == timedelta(days=7)


def test_cadence_delta_unknown_raises() -> None:
    with pytest.raises(ValueError):
        cadence_delta("never")


def test_is_due_uses_next_run_at() -> None:
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    s = ReportSchedule(
        name="x", report_name="kpi", params={}, cadence="daily",
        enabled=True, next_run_at=now - timedelta(minutes=1),
    )
    assert is_due(s, now) is True


def test_is_due_returns_false_when_disabled() -> None:
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    s = ReportSchedule(
        name="x", report_name="kpi", params={}, cadence="daily",
        enabled=False, next_run_at=None,
    )
    assert is_due(s, now) is False


def test_materialize_params_resolves_now_and_negatives() -> None:
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    params = {"since": "-1d", "until": "now", "device_id": "abc"}
    out = materialize_params(params, now)
    assert out["device_id"] == "abc"
    assert out["until"] == now.isoformat()
    assert out["since"] == (now - timedelta(days=1)).isoformat()


def test_materialize_params_ignores_unknown_units() -> None:
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    params = {"since": "-2x"}
    out = materialize_params(params, now)
    assert out["since"] == "-2x"
