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
from app.services.topology.credentials import build_credentials_map

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
    credentials_map = await build_credentials_map(db, devices)
    await builder.build_full(devices=devices, credentials_map=credentials_map)
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
    credentials_map = await build_credentials_map(db, [device])
    await builder.build_full(devices=[device], credentials_map=credentials_map)
    return {"rebuilt": 1, "device_id": str(id)}
