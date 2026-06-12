"""Assurance API — health score, correlation groups, and event timeline.

Routes are split across focused submodules and assembled here. Helper
functions and schemas are re-exported for backwards compatibility with
existing imports (tests, ``app.services.assurance.snapshot_trigger``).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.assurance import groups, history, services_impact, summary, topology
from app.api.assurance.groups import suppress_group, unsuppress_group
from app.api.assurance.history import _bucket_snapshots
from app.api.assurance.schemas import (
    AssuranceSummary,
    CorrelationGroup,
    GroupLifecycleRequest,
    GroupLifecycleResponse,
    ImpactedDevice,
    ImpactedInterface,
    NetworkScorePoint,
    ServiceAlert,
    ServiceDependencyImpact,
    ServiceImpact,
    ServiceImpactMember,
    ServiceScorePoint,
    TimelineEvent,
    TopologyImpactNode,
    TopologyImpactResponse,
)
from app.api.assurance.scoring import (
    _SEVERITY_ORDER,
    _build_groups,
    _compute_service_impact,
    _health_state,
    _interface_alarm_match,
)
from app.api.assurance.services_impact import _persist_service_score_snapshots

router = APIRouter()
router.include_router(summary.router)
router.include_router(groups.router)
router.include_router(services_impact.router)
router.include_router(history.router)
router.include_router(topology.router)

__all__ = [
    "AssuranceSummary",
    "CorrelationGroup",
    "GroupLifecycleRequest",
    "GroupLifecycleResponse",
    "ImpactedDevice",
    "ImpactedInterface",
    "NetworkScorePoint",
    "ServiceAlert",
    "ServiceDependencyImpact",
    "ServiceImpact",
    "ServiceImpactMember",
    "ServiceScorePoint",
    "TimelineEvent",
    "TopologyImpactNode",
    "TopologyImpactResponse",
    "_SEVERITY_ORDER",
    "_bucket_snapshots",
    "_build_groups",
    "_compute_service_impact",
    "_health_state",
    "_interface_alarm_match",
    "_persist_service_score_snapshots",
    "router",
    "suppress_group",
    "unsuppress_group",
]
