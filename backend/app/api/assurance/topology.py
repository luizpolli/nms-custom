"""Role-aware topology blast-radius (impact) endpoint."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assurance.schemas import TopologyImpactNode, TopologyImpactResponse
from app.database import get_db
from app.models.topology import TopologyLink, TopologyNode
from app.services.assurance.topology_impact import compute_topology_blast_radius

router = APIRouter()


def _node_label(node: TopologyNode) -> str:
    return node.device.name if node.device else node.node_id


def _impact_node(
    node: TopologyNode,
    depth: int,
    *,
    via_link_id: uuid.UUID | None = None,
    direction: str = "outbound",
    confidence: str = "high",
    reason: str = "directed-link",
) -> TopologyImpactNode:
    return TopologyImpactNode(
        node_id=node.node_id,
        device_id=node.device_id,
        label=_node_label(node),
        depth=depth,
        role=node.role,
        via_link_id=via_link_id,
        direction=direction,
        confidence=confidence,
        reason=reason,
    )


@router.get("/impact", response_model=TopologyImpactResponse)
async def topology_impact(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: uuid.UUID | None = None,
    node_id: str | None = None,
    max_depth: int = 3,
    traversal_mode: str = "auto",
) -> TopologyImpactResponse:
    """Return role-aware topology blast radius from a root device/node.

    ``auto`` follows directed links and safely explores reverse edges when
    discovery orientation is ambiguous or role hierarchy suggests the persisted
    edge points upstream.
    """
    nodes_result = await db.execute(select(TopologyNode))
    nodes = list(nodes_result.scalars().all())
    if not nodes:
        return TopologyImpactResponse(root=None, impacted_nodes=[], impacted_count=0, max_depth=max_depth, traversal_mode=traversal_mode)

    root = None
    for node in nodes:
        if device_id and node.device_id == device_id:
            root = node
            break
        if node_id and node.node_id == node_id:
            root = node
            break
    if root is None:
        root = nodes[0]

    links_result = await db.execute(select(TopologyLink))
    depth_limit = max(1, min(max_depth, 10))
    graph = compute_topology_blast_radius(
        root=root,
        nodes=nodes,
        links=list(links_result.scalars().all()),
        max_depth=depth_limit,
        traversal_mode=traversal_mode,
    )

    impacted = [
        _impact_node(
            step.node,
            step.depth,
            via_link_id=step.via_link_id,
            direction=step.direction,
            confidence=step.confidence,
            reason=step.reason,
        )
        for step in graph.impacted
    ]
    return TopologyImpactResponse(
        root=_impact_node(root, 0),
        impacted_nodes=impacted,
        impacted_count=len(impacted),
        max_depth=depth_limit,
        traversal_mode=graph.traversal_mode,
        ambiguous_edge_count=graph.ambiguous_edge_count,
    )
