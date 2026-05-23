"""Tests for service-level impact computation in assurance API."""

import uuid
from datetime import datetime, timezone

from app.api.assurance import _compute_service_impact
from app.models.alarm import Alarm
from app.models.service import Service, ServiceDependency, ServiceMember


def _alarm(device_id=None, severity="major", state="active") -> Alarm:
    now = datetime.now(timezone.utc)
    return Alarm(
        id=uuid.uuid4(),
        device_id=device_id,
        source_host="r1",
        severity=severity,
        category="link",
        event_type="linkDown",
        message="Link down",
        state=state,
        first_seen=now,
        last_seen=now,
        occurrence_count=1,
        raw_varbinds={},
    )


def _service_with_members(device_ids):
    members = []
    for did in device_ids:
        members.append(
            ServiceMember(
                id=uuid.uuid4(),
                device_id=did,
                role="member",
                weight=1.0,
            )
        )
    return Service(
        id=uuid.uuid4(),
        name="svc-test",
        kind="customer",
        members=members,
    )


def test_service_impact_healthy_when_no_alarms():
    d1 = uuid.uuid4()
    svc = _service_with_members([d1])
    impact = _compute_service_impact(svc, {}, {}, {})
    assert impact.score == 100
    assert impact.health_state == "healthy"
    assert impact.member_count == 1
    assert impact.impacted_member_count == 0
    assert impact.active_alarm_count == 0


def test_service_impact_drops_with_critical_alarm():
    d1 = uuid.uuid4()
    svc = _service_with_members([d1])
    alarms_by_device = {d1: [_alarm(device_id=d1, severity="critical")]}
    impact = _compute_service_impact(svc, alarms_by_device, {}, {})
    assert impact.score < 100
    assert impact.active_alarm_count == 1
    assert impact.worst_severity == "critical"
    assert impact.impacted_member_count == 1


def test_service_impact_weighted_average():
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    svc = _service_with_members([d1, d2])
    # d1 (weight 1) has critical alarm; d2 (weight 1) has no alarm
    alarms_by_device = {d1: [_alarm(device_id=d1, severity="critical")]}
    impact = _compute_service_impact(svc, alarms_by_device, {}, {})
    assert impact.member_count == 2
    # Should be between member scores
    assert 0 < impact.score < 100


def test_service_impact_interface_down_penalty():
    iface_id = uuid.uuid4()
    member = ServiceMember(id=uuid.uuid4(), interface_id=iface_id, role="member", weight=1.0)
    svc = Service(id=uuid.uuid4(), name="svc-iface", kind="infrastructure", members=[member])
    impact = _compute_service_impact(svc, {}, {}, {iface_id: "down"})
    assert impact.score < 100
    assert impact.impacted_member_count == 1


def test_service_impact_handles_no_members():
    svc = Service(id=uuid.uuid4(), name="svc-empty", kind="other", members=[])
    impact = _compute_service_impact(svc, {}, {}, {})
    assert impact.score == 100
    assert impact.member_count == 0


def test_service_impact_dependency_penalty_propagates():
    downstream = Service(id=uuid.uuid4(), name="customer-vpn", kind="customer", members=[])
    upstream = Service(id=uuid.uuid4(), name="core-transport", kind="transport", members=[])
    dep = ServiceDependency(
        id=uuid.uuid4(),
        source_service_id=downstream.id,
        target_service_id=upstream.id,
        target_service=upstream,
        weight=1.0,
        is_critical=True,
        direction="source_to_target",
    )
    downstream.upstream_dependencies = [dep]
    impact = _compute_service_impact(downstream, {}, {}, {}, {upstream.id: 50})
    assert impact.base_score == 100
    assert impact.score < 100
    assert impact.dependency_penalty > 0
    assert impact.dependency_impacts[0].target_service_name == "core-transport"
    assert impact.evidence is not None
    assert impact.evidence["dependency_penalty"] == impact.dependency_penalty
    assert impact.evidence["dependency_impacts"][0]["dependency_id"] == str(dep.id)


def test_service_impact_healthy_dependency_does_not_penalize():
    downstream = Service(id=uuid.uuid4(), name="customer-vpn", kind="customer", members=[])
    upstream = Service(id=uuid.uuid4(), name="core-transport", kind="transport", members=[])
    downstream.upstream_dependencies = [
        ServiceDependency(
            id=uuid.uuid4(),
            source_service_id=downstream.id,
            target_service_id=upstream.id,
            target_service=upstream,
            weight=1.0,
            is_critical=True,
        )
    ]
    impact = _compute_service_impact(downstream, {}, {}, {}, {upstream.id: 95})
    assert impact.score == 100
    assert impact.dependency_penalty == 0
    assert impact.dependency_impacts == []


def test_service_impact_direction_override_none_suppresses_penalty():
    downstream = Service(id=uuid.uuid4(), name="customer-vpn", kind="customer", members=[])
    upstream = Service(id=uuid.uuid4(), name="core-transport", kind="transport", members=[])
    dep = ServiceDependency(
        id=uuid.uuid4(),
        source_service_id=downstream.id,
        target_service_id=upstream.id,
        target_service=upstream,
        weight=10.0,
        is_critical=True,
        direction="source_to_target",
        direction_override="none",
    )
    downstream.upstream_dependencies = [dep]

    impact = _compute_service_impact(downstream, {}, {}, {}, {upstream.id: 10})

    assert impact.score == 100
    assert impact.dependency_penalty == 0
    assert impact.dependency_impacts == []
    assert impact.evidence is not None
    assert impact.evidence["dependency_impacts"] == []
