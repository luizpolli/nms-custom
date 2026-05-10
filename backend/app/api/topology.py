"""Topology API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.device import Device
from app.services.snmp.engine import SNMPEngine
from app.services.topology.builder import TopologyBuilder

router = APIRouter()


class GraphResponse(BaseModel):
    nodes: list[dict]
    links: list[dict]


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GraphResponse:
    snmp = SNMPEngine()
    builder = TopologyBuilder(snmp_engine=snmp, session_factory=async_session_factory)
    graph = await builder.export_graph()
    if isinstance(graph, dict):
        return GraphResponse(nodes=graph.get("nodes", []), links=graph.get("links", []))
    return GraphResponse(nodes=[], links=[])


@router.post("/rebuild")
async def rebuild_all(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    snmp = SNMPEngine()
    builder = TopologyBuilder(snmp_engine=snmp, session_factory=async_session_factory)
    result = await db.execute(select(Device))
    devices = result.scalars().all()
    await builder.build_full(devices=devices)
    return {"rebuilt": len(devices)}


@router.post("/devices/{id}/rebuild")
async def rebuild_device(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(Device).where(Device.id == id))
    device = result.scalar_one_or_none()
    if device is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Device not found")
    snmp = SNMPEngine()
    builder = TopologyBuilder(snmp_engine=snmp, session_factory=async_session_factory)
    await builder.build_full(devices=[device])
    return {"rebuilt": 1, "device_id": str(id)}
