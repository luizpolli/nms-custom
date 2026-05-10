"""Discovery API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.discovery.engine import DiscoveryEngine
from app.services.snmp.engine import SNMPEngine

router = APIRouter()


class DiscoveryScanRequest(BaseModel):
    cidr: str
    communities: list[str] = ["public"]


@router.post("/scan")
async def scan_subnet(
    body: DiscoveryScanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    snmp = SNMPEngine()
    engine = DiscoveryEngine(snmp_engine=snmp, db=db)
    result = await engine.scan_subnet(body.cidr, body.communities)
    await engine.persist(result)
    return result if isinstance(result, dict) else {"result": result}


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID) -> dict:
    raise HTTPException(status_code=404, detail="background jobs not implemented yet")
