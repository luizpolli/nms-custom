"""Topology blast-radius helpers for assurance impact analysis."""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from app.models.topology import TopologyLink, TopologyNode

# Lower rank is closer to the network/service core. Unknown roles are treated as
# ambiguous so discovered links can still be explored bidirectionally.
_ROLE_RANK = {
    "core": 0,
    "spine": 0,
    "aggregation": 1,
    "agg": 1,
    "distribution": 2,
    "dist": 2,
    "border": 2,
    "edge": 3,
    "leaf": 3,
    "access": 4,
    "customer": 5,
    "cpe": 5,
    "endpoint": 6,
}


@dataclass(frozen=True, slots=True)
class ImpactStep:
    """One impacted topology node reached during blast-radius traversal."""

    node: TopologyNode
    depth: int
    via_link_id: uuid.UUID | None = None
    direction: str = "outbound"
    confidence: str = "high"
    reason: str = "directed-link"


@dataclass(frozen=True, slots=True)
class ImpactGraph:
    """Computed topology blast radius from one root node."""

    root: TopologyNode
    impacted: list[ImpactStep]
    traversal_mode: str
    ambiguous_edge_count: int


def _role_rank(role: str | None) -> int | None:
    if not role:
        return None
    return _ROLE_RANK.get(role.strip().lower())


def _edge_orientation(source: TopologyNode, target: TopologyNode) -> tuple[str, str]:
    """Return preferred source->target confidence/reason from topology roles."""
    source_rank = _role_rank(source.role)
    target_rank = _role_rank(target.role)
    if source_rank is None or target_rank is None or source_rank == target_rank:
        return "medium", "ambiguous-discovery-edge"
    if source_rank < target_rank:
        return "high", "role-downstream"
    return "low", "role-upstream"


def compute_topology_blast_radius(
    *,
    root: TopologyNode,
    nodes: Iterable[TopologyNode],
    links: Iterable[TopologyLink],
    max_depth: int = 3,
    traversal_mode: str = "auto",
) -> ImpactGraph:
    """Compute role-aware topology blast radius.

    ``auto`` follows source->target links and also explores reverse directions
    when roles imply the discovered edge may be oriented upstream or when one of
    the roles is unknown. This catches common LLDP/CDP ambiguity without
    mutating persisted topology.
    """
    depth_limit = max(1, min(max_depth, 10))
    mode = traversal_mode if traversal_mode in {"auto", "downstream", "upstream", "bidirectional"} else "auto"
    node_by_id = {n.id: n for n in nodes}
    outgoing: dict[uuid.UUID, list[TopologyLink]] = defaultdict(list)
    incoming: dict[uuid.UUID, list[TopologyLink]] = defaultdict(list)
    ambiguous_edges = 0

    for link in links:
        outgoing[link.source_node_id].append(link)
        incoming[link.target_node_id].append(link)
        src = node_by_id.get(link.source_node_id)
        dst = node_by_id.get(link.target_node_id)
        if src and dst and _edge_orientation(src, dst)[1] == "ambiguous-discovery-edge":
            ambiguous_edges += 1

    visited = {root.id}
    queue: deque[tuple[uuid.UUID, int]] = deque([(root.id, 0)])
    impacted: list[ImpactStep] = []

    def _candidate_edges(current_id: uuid.UUID) -> list[tuple[TopologyLink, uuid.UUID, str, str, str]]:
        current = node_by_id[current_id]
        candidates: list[tuple[TopologyLink, uuid.UUID, str, str, str]] = []
        if mode in {"auto", "downstream", "bidirectional"}:
            for link in outgoing.get(current_id, []):
                target = node_by_id.get(link.target_node_id)
                if target:
                    confidence, reason = _edge_orientation(current, target)
                    candidates.append((link, target.id, "outbound", confidence, reason))
        if mode in {"upstream", "bidirectional"}:
            for link in incoming.get(current_id, []):
                source = node_by_id.get(link.source_node_id)
                if source:
                    confidence, reason = _edge_orientation(source, current)
                    candidates.append((link, source.id, "inbound", confidence, reason))
        if mode == "auto":
            # Add reverse traversal for uncertain or apparently upstream-oriented
            # edges so blast radius does not silently miss discovered neighbors.
            for link in incoming.get(current_id, []):
                source = node_by_id.get(link.source_node_id)
                if not source:
                    continue
                confidence, reason = _edge_orientation(source, current)
                if reason == "ambiguous-discovery-edge" or confidence == "low":
                    candidates.append((link, source.id, "inbound", "medium", "auto-reverse-ambiguous"))
        return candidates

    while queue:
        current_id, depth = queue.popleft()
        if depth >= depth_limit:
            continue
        for link, next_id, direction, confidence, reason in _candidate_edges(current_id):
            if next_id in visited or next_id not in node_by_id:
                continue
            visited.add(next_id)
            next_depth = depth + 1
            impacted.append(
                ImpactStep(
                    node=node_by_id[next_id],
                    depth=next_depth,
                    via_link_id=link.id,
                    direction=direction,
                    confidence=confidence,
                    reason=reason,
                )
            )
            queue.append((next_id, next_depth))

    impacted.sort(key=lambda s: (s.depth, {"high": 0, "medium": 1, "low": 2}.get(s.confidence, 3), s.node.node_id))
    return ImpactGraph(root=root, impacted=impacted, traversal_mode=mode, ambiguous_edge_count=ambiguous_edges)
