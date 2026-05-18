"""Tests for service threshold alerts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.api.assurance import ServiceAlert, _compute_service_impact
from app.models.alarm import Alarm
from app.models.service import Service, ServiceMember


def _service(name: str, *, target: int | None, device_ids: list[uuid.UUID]) -> Service:
    members = [
        ServiceMember(id=uuid.uuid4(), device_id=d, role="member", weight=1.0) for d in device_ids
    ]
    return Service(id=uuid.uuid4(), name=name, kind="customer", target_score=target, members=members)


def _alarm(device_id: uuid.UUID, severity: str = "critical") -> Alarm:
    now = datetime.now(timezone.utc)
    return Alarm(
        id=uuid.uuid4(),
        device_id=device_id,
        source_host="r1",
        severity=severity,
        category="link",
        event_type="linkDown",
        message="Link down",
        state="active",
        first_seen=now,
        last_seen=now,
        occurrence_count=1,
        raw_varbinds={},
    )


def test_breach_when_score_below_explicit_target():
    d = uuid.uuid4()
    svc = _service("svc-a", target=95, device_ids=[d])
    impact = _compute_service_impact(svc, {d: [_alarm(d, "critical")]}, {}, {})
    assert impact.score < 95
    alert = ServiceAlert(
        service_id=impact.service_id,
        name=impact.name,
        kind=impact.kind,
        score=impact.score,
        target_score=95,
        deficit=95 - impact.score,
        health_state=impact.health_state,
        worst_severity=impact.worst_severity,
        impacted_member_count=impact.impacted_member_count,
        active_alarm_count=impact.active_alarm_count,
    )
    assert alert.deficit > 0


def test_healthy_service_does_not_alert_against_default_target():
    d = uuid.uuid4()
    svc = _service("svc-clean", target=None, device_ids=[d])
    impact = _compute_service_impact(svc, {}, {}, {})
    assert impact.score >= 90


def test_explicit_lower_target_avoids_alert_on_minor_dip():
    d = uuid.uuid4()
    svc = _service("svc-relaxed", target=50, device_ids=[d])
    impact = _compute_service_impact(svc, {d: [_alarm(d, "minor")]}, {}, {})
    assert impact.score >= 50, "minor alarm shouldn't drop score below relaxed 50 target"
