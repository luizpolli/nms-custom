"""Topology builder — discovers neighbors via LLDP/CDP and maintains the
topology_nodes / topology_links tables.

    engine = SNMPEngine()
    builder = TopologyBuilder(engine, async_session_factory)
    stats = await builder.build_for_device(device, credential)
    graph = await builder.export_graph()
"""

from __future__ import annotations

import uuid
from typing import Callable

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.topology import TopologyLink, TopologyNode
from app.services.snmp.engine import SNMPEngine
from app.services.snmp.poller import SNMPCredential

SessionFactory = Callable[[], AsyncSession]


def _node_key(device: Device | None, neighbor: dict) -> str:
    """Deterministic node key — prefer device UUID, else ext:<sys_name>."""
    if device is not None:
        return str(device.id)
    sys_name = neighbor.get("sys_name") or neighbor.get("device_id") or ""
    return f"ext:{sys_name}" if sys_name else f"ext:anon:{uuid.uuid4()}"


def _link_canonical(a: str, b: str) -> tuple[str, str]:
    """Return (source, target) in lexicographic order for dedup."""
    return (a, b) if a <= b else (b, a)


class TopologyBuilder:
    """Builds and persists network topology from SNMP LLDP/CDP discovery."""

    def __init__(self, snmp_engine: SNMPEngine, session_factory: SessionFactory) -> None:
        self._engine = snmp_engine
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_for_device(self, device: Device, credential: SNMPCredential) -> dict:
        """Discover neighbors of one device and upsert nodes + links."""
        host = device.ip_address
        lldp = await self._engine.discover_lldp_neighbors(host, credential)
        cdp = await self._engine.discover_cdp_neighbors(host, credential)
        neighbors = _merge_neighbors(lldp, cdp)

        nodes_added = links_added = 0
        src_key = str(device.id)

        async with self._sf() as session:
            await _upsert_node(session, src_key, device_id=device.id, role=device.device_type)

            for nb in neighbors:
                matched = await self._match_neighbor_to_device(nb, session)
                nb_key = _node_key(matched, nb)
                nb_device_id = matched.id if matched else None
                created = await _upsert_node(session, nb_key, device_id=nb_device_id)
                if created:
                    nodes_added += 1

                src_iface = nb.get("port_desc") or nb.get("device_port")
                tgt_iface = nb.get("port_id")
                link_created = await _upsert_link(
                    session, src_key, nb_key, src_iface, tgt_iface, "lldp" if nb in lldp else "cdp"
                )
                if link_created:
                    links_added += 1

            await session.commit()

        logger.info("build_for_device {}: +{} nodes +{} links", host, nodes_added, links_added)
        return {"nodes_added": nodes_added, "links_added": links_added}

    async def build_full(
        self,
        devices: list[Device],
        credentials_map: dict[uuid.UUID, SNMPCredential],
    ) -> dict:
        """Run discovery for all devices; bidirectional link dedup is automatic."""
        total_nodes = total_links = 0
        for dev in devices:
            cred = credentials_map.get(dev.id) or credentials_map.get(dev.credential_id)
            if cred is None:
                logger.warning("No credential for device {}; skipping", dev.name)
                continue
            stats = await self.build_for_device(dev, cred)
            total_nodes += stats["nodes_added"]
            total_links += stats["links_added"]
        return {"nodes_added": total_nodes, "links_added": total_links}

    async def export_graph(self) -> dict:
        """Return {nodes, links} ready for the frontend."""
        async with self._sf() as session:
            nodes_res = await session.execute(select(TopologyNode))
            links_res = await session.execute(select(TopologyLink))

        nodes = [
            {
                "id": n.node_id,
                "label": n.device.name if n.device else n.node_id,
                "role": n.role,
                "position": {"x": n.position_x, "y": n.position_y},
            }
            for n in nodes_res.scalars().all()
        ]
        links = [
            {
                "source": lnk.source_node_id,
                "target": lnk.target_node_id,
                "source_iface": lnk.source_interface,
                "target_iface": lnk.target_interface,
            }
            for lnk in links_res.scalars().all()
        ]
        return {"nodes": nodes, "links": links}

    async def _match_neighbor_to_device(
        self, neighbor: dict, session: AsyncSession
    ) -> Device | None:
        """Best-effort lookup: try sys_name then chassis_id as IP."""
        sys_name = neighbor.get("sys_name") or neighbor.get("device_id")
        if sys_name:
            res = await session.execute(select(Device).where(Device.name == sys_name).limit(1))
            found = res.scalar_one_or_none()
            if found:
                return found

        addr = neighbor.get("address") or neighbor.get("chassis_id")
        if addr:
            res = await session.execute(select(Device).where(Device.ip_address == addr).limit(1))
            return res.scalar_one_or_none()

        return None


# ------------------------------------------------------------------
# Helpers (module-level, short)
# ------------------------------------------------------------------

def _merge_neighbors(lldp: list[dict], cdp: list[dict]) -> list[dict]:
    """Merge LLDP + CDP neighbor lists; LLDP wins on same sys_name conflict."""
    merged: dict[str, dict] = {}
    for nb in cdp:
        key = nb.get("device_id") or nb.get("address") or str(id(nb))
        merged[key] = nb
    for nb in lldp:
        key = nb.get("sys_name") or nb.get("chassis_id") or str(id(nb))
        merged[key] = nb  # LLDP overwrites
    return list(merged.values())


async def _upsert_node(
    session: AsyncSession,
    node_id: str,
    device_id: uuid.UUID | None = None,
    role: str | None = None,
) -> bool:
    """Insert node if absent; return True if newly created."""
    res = await session.execute(select(TopologyNode).where(TopologyNode.node_id == node_id).limit(1))
    if res.scalar_one_or_none() is not None:
        return False
    node = TopologyNode(node_id=node_id, device_id=device_id, role=role)
    session.add(node)
    return True


async def _upsert_link(
    session: AsyncSession,
    src: str,
    tgt: str,
    src_iface: str | None,
    tgt_iface: str | None,
    method: str,
) -> bool:
    """Insert link if no matching canonical link exists; return True if created."""
    a, b = _link_canonical(src, tgt)
    res = await session.execute(
        select(TopologyLink).where(
            TopologyLink.source_node_id == a,
            TopologyLink.target_node_id == b,
        ).limit(1)
    )
    if res.scalar_one_or_none() is not None:
        return False
    link = TopologyLink(
        source_node_id=a,
        target_node_id=b,
        source_interface=src_iface if a == src else tgt_iface,
        target_interface=tgt_iface if a == src else src_iface,
        discovery_method=method,
    )
    session.add(link)
    return True
