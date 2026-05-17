"""Tests for KPI threshold (TCA) evaluator predicates."""

from __future__ import annotations

import pytest

from app.models.kpi_threshold import KPIThreshold
from app.services.kpi.thresholds import crossed, should_clear


def _threshold(**overrides) -> KPIThreshold:
    defaults = dict(
        name="cpu",
        kpi_type="cpu_utilization",
        operator="gt",
        value=80.0,
        clear_value=None,
        severity="major",
        auto_clear=True,
        enabled=True,
        consecutive_samples=1,
    )
    defaults.update(overrides)
    return KPIThreshold(**defaults)


def test_crossed_gt_returns_true_when_value_above() -> None:
    assert crossed(_threshold(operator="gt", value=80), 90) is True


def test_crossed_gt_returns_false_when_value_equal() -> None:
    assert crossed(_threshold(operator="gt", value=80), 80) is False


def test_crossed_gte_returns_true_when_value_equal() -> None:
    assert crossed(_threshold(operator="gte", value=80), 80) is True


def test_crossed_lt_returns_true_when_value_below() -> None:
    assert crossed(_threshold(operator="lt", value=10), 5) is True


def test_crossed_unknown_operator_returns_false() -> None:
    assert crossed(_threshold(operator="??"), 100) is False


def test_should_clear_without_hysteresis_uses_inverse() -> None:
    t = _threshold(operator="gt", value=80, clear_value=None, auto_clear=True)
    assert should_clear(t, 50) is True
    assert should_clear(t, 90) is False


def test_should_clear_with_hysteresis_uses_clear_value() -> None:
    t = _threshold(operator="gt", value=80, clear_value=70, auto_clear=True)
    assert should_clear(t, 75) is False  # between clear and threshold, do not clear
    assert should_clear(t, 65) is True   # under hysteresis line


def test_should_clear_disabled_returns_false() -> None:
    t = _threshold(operator="gt", value=80, auto_clear=False)
    assert should_clear(t, 0) is False


@pytest.mark.parametrize("operator,value,target,expected", [
    ("gt", 81, 80, True),
    ("gte", 80, 80, True),
    ("lt", 79, 80, True),
    ("lte", 80, 80, True),
])
def test_crossed_parametrized(operator: str, value: float, target: float, expected: bool) -> None:
    assert crossed(_threshold(operator=operator, value=target), value) is expected
