import uuid

from app.models.topology import TopologyLink, TopologyNode
from app.services.assurance.topology_impact import compute_topology_blast_radius


def _node(name: str, role: str | None) -> TopologyNode:
    return TopologyNode(id=uuid.uuid4(), node_id=name, role=role)


def _link(source: TopologyNode, target: TopologyNode) -> TopologyLink:
    return TopologyLink(id=uuid.uuid4(), source_node_id=source.id, target_node_id=target.id)


def test_auto_blast_radius_follows_role_downstream():
    core = _node("core-1", "core")
    dist = _node("dist-1", "distribution")
    access = _node("access-1", "access")

    graph = compute_topology_blast_radius(
        root=core,
        nodes=[core, dist, access],
        links=[_link(core, dist), _link(dist, access)],
        max_depth=3,
    )

    assert [step.node.node_id for step in graph.impacted] == ["dist-1", "access-1"]
    assert all(step.confidence == "high" for step in graph.impacted)


def test_auto_blast_radius_reverses_ambiguous_discovery_edge():
    core = _node("core-1", "core")
    access = _node("access-1", "access")

    graph = compute_topology_blast_radius(
        root=core,
        nodes=[core, access],
        links=[_link(access, core)],  # common LLDP/CDP orientation ambiguity
        max_depth=2,
    )

    assert [step.node.node_id for step in graph.impacted] == ["access-1"]
    assert graph.impacted[0].direction == "inbound"
    assert graph.impacted[0].reason == "auto-reverse-ambiguous"


def test_bidirectional_mode_walks_neighbors_regardless_of_direction():
    core = _node("core-1", "core")
    peer = _node("peer-1", "core")

    graph = compute_topology_blast_radius(
        root=core,
        nodes=[core, peer],
        links=[_link(peer, core)],
        traversal_mode="bidirectional",
        max_depth=1,
    )

    assert [step.node.node_id for step in graph.impacted] == ["peer-1"]
    assert graph.ambiguous_edge_count == 1
