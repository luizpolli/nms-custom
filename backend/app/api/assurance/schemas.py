"""Pydantic response/request models for the assurance API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ImpactedDevice(BaseModel):
    device_id: uuid.UUID | None = None
    name: str
    source_host: str | None = None
    score: int
    active_alarms: int
    worst_severity: str
    last_seen: datetime | None = None


class ImpactedInterface(BaseModel):
    interface_id: uuid.UUID
    device_id: uuid.UUID
    name: str
    score: int
    oper_status: str | None = None
    active_alarms: int = 0
    baseline_breaches: int = 0
    worst_severity: str = "info"


class CorrelationGroup(BaseModel):
    group_key: str
    root_alarm_id: uuid.UUID | None = None
    root_cause: str
    severity: str
    category: str
    state: str
    active_count: int
    occurrence_count: int
    impacted_devices: list[str] = Field(default_factory=list)
    first_seen: datetime
    last_seen: datetime


class TimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    severity: str
    source_type: str
    source_host: str
    message: str
    correlation_key: str | None = None
    device_id: uuid.UUID | None = None
    object_type: str | None = None
    object_id: str | None = None


class TopologyImpactNode(BaseModel):
    node_id: str
    device_id: uuid.UUID | None = None
    label: str
    depth: int
    role: str | None = None
    via_link_id: uuid.UUID | None = None
    direction: str = "outbound"
    confidence: str = "high"
    reason: str = "directed-link"


class TopologyImpactResponse(BaseModel):
    root: TopologyImpactNode | None = None
    impacted_nodes: list[TopologyImpactNode]
    impacted_count: int
    max_depth: int
    traversal_mode: str = "auto"
    ambiguous_edge_count: int = 0


class GroupLifecycleRequest(BaseModel):
    by_user: str
    reason: str = ""


class GroupLifecycleResponse(BaseModel):
    group_key: str
    state: str
    affected_alarm_count: int


class ServiceImpactMember(BaseModel):
    member_id: uuid.UUID
    device_id: uuid.UUID | None = None
    interface_id: uuid.UUID | None = None
    label: str
    role: str
    weight: float
    score: int
    active_alarms: int
    worst_severity: str


class ServiceDependencyImpact(BaseModel):
    dependency_id: uuid.UUID
    target_service_id: uuid.UUID
    target_service_name: str
    target_score: int
    propagated_penalty: int
    weight: float
    is_critical: bool
    direction: str
    direction_override: str = "auto"
    effective_direction: str = "source_to_target"


class ServiceImpact(BaseModel):
    service_id: uuid.UUID
    name: str
    kind: str
    description: str | None = None
    score: int
    base_score: int | None = None
    dependency_penalty: int = 0
    health_state: str
    member_count: int
    impacted_member_count: int
    active_alarm_count: int
    worst_severity: str
    members: list[ServiceImpactMember] = Field(default_factory=list)
    dependency_impacts: list[ServiceDependencyImpact] = Field(default_factory=list)
    evidence: dict | None = None


class AssuranceSummary(BaseModel):
    network_score: int
    health_state: str
    active_alarm_count: int
    active_group_count: int
    impacted_device_count: int
    impacted_interface_count: int
    baseline_breach_count: int
    top_impacted_devices: list[ImpactedDevice]
    top_impacted_interfaces: list[ImpactedInterface]
    top_groups: list[CorrelationGroup]


class ServiceAlert(BaseModel):
    service_id: uuid.UUID
    name: str
    kind: str
    score: int
    target_score: int
    deficit: int
    health_state: str
    worst_severity: str
    impacted_member_count: int
    active_alarm_count: int


class ServiceScorePoint(BaseModel):
    captured_at: datetime
    score: int
    base_score: int | None = None
    dependency_penalty: int = 0
    health_state: str
    evidence: dict | None = None


class NetworkScorePoint(BaseModel):
    bucket_start: datetime
    avg_score: float
    min_score: int
    max_score: int
    sample_count: int
    service_count: int
