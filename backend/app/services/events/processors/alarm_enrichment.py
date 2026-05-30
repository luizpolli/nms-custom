"""Alarm enrichment processor.

Subscribes to alarm events and enriches the matching Alarm record with:
  - Device metadata (name, role, site, model)
  - Interface metadata when the event carries an if_index
  - Topology context (upstream/downstream L2/L3 neighbours)
  - Prior occurrence count and last-seen for the correlation key

Idempotent: re-processing the same event_id is a no-op after the first pass.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm
from app.models.device import Device
from app.models.interface import Interface
from app.models.topology import TopologyLink, TopologyNode

SessionFactory = Callable[[], AsyncSession]


class AlarmEnrichmentProcessor:
    """Enrich an Alarm record from device, interface, and topology metadata."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sf = session_factory

    async def enrich(self, alarm: Alarm, *, if_index: int | None = None) -> dict[str, Any]:
        """Return enrichment dict and persist it into alarm.raw_varbinds['_enrichment'].

        Idempotent: if ``alarm.raw_varbinds['_enrichment']`` already contains an
        entry keyed by this alarm's event processing pass, it is returned as-is.
        """
        existing = (alarm.raw_varbinds or {}).get("_enrichment")
        if existing:
            return existing

        enrichment: dict[str, Any] = {}
        async with self._sf() as session:
            if alarm.device_id:
                device = await session.get(Device, alarm.device_id)
                if device is not None:
                    enrichment["device"] = {
                        "name": device.name,
                        "role": device.role,
                        "site": device.site_id,
                        "model": device.model,
                    }
                    if if_index is not None:
                        iface = await self._find_interface(session, alarm.device_id, if_index)
                        if iface is not None:
                            enrichment["interface"] = {
                                "name": iface.name,
                                "description": iface.description,
                                "oper_status": iface.oper_status,
                                "admin_status": iface.admin_status,
                            }
                    enrichment["topology"] = await self._topology_context(session, alarm.device_id)

            enrichment["prior_occurrences"] = alarm.occurrence_count
            enrichment["last_seen"] = alarm.last_seen.isoformat() if alarm.last_seen else None

        if enrichment:
            varbinds = dict(alarm.raw_varbinds or {})
            varbinds["_enrichment"] = enrichment
            alarm.raw_varbinds = varbinds
            async with self._sf() as session:
                merged = await session.merge(alarm)
                await session.commit()
                alarm.raw_varbinds = merged.raw_varbinds

        return enrichment

    async def _find_interface(
        self, session: AsyncSession, device_id: uuid.UUID, if_index: int
    ) -> Interface | None:
        result = await session.execute(
            select(Interface)
            .where(Interface.device_id == device_id, Interface.if_index == if_index)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _topology_context(
        self, session: AsyncSession, device_id: uuid.UUID
    ) -> dict[str, list[str]]:
        node_result = await session.execute(
            select(TopologyNode).where(TopologyNode.device_id == device_id).limit(1)
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            return {}

        upstream: list[str] = []
        downstream: list[str] = []

        links_result = await session.execute(
            select(TopologyLink).where(
                (TopologyLink.source_node_id == node.id)
                | (TopologyLink.target_node_id == node.id)
            )
        )
        links = links_result.scalars().all()

        for link in links:
            peer_node_id = link.target_node_id if link.source_node_id == node.id else link.source_node_id
            peer_result = await session.execute(
                select(TopologyNode).where(TopologyNode.id == peer_node_id).limit(1)
            )
            peer = peer_result.scalar_one_or_none()
            if peer is None:
                continue
            label = peer.node_id
            if link.source_node_id == node.id:
                downstream.append(label)
            else:
                upstream.append(label)

        return {"upstream": upstream, "downstream": downstream}
