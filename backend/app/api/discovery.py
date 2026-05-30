"""Discovery API routes."""

from __future__ import annotations

import ipaddress
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.services.discovery.engine import DiscoveryEngine
from app.services.snmp.engine import SNMPEngine

router = APIRouter()


class DiscoveryScanRequest(BaseModel):
    cidr: str = Field(..., max_length=64)
    communities: list[str] = Field(default_factory=lambda: ["public"], min_length=1, max_length=10)

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str) -> str:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError("Invalid CIDR") from exc
        if network.num_addresses > settings.discovery_max_hosts:
            raise ValueError(f"CIDR too large; max {settings.discovery_max_hosts} addresses")
        return str(network)

    @field_validator("communities")
    @classmethod
    def validate_communities(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or len(value) > 128 or any(ch in value for ch in "\r\n\x00"):
                raise ValueError("Invalid SNMP community value")
        return values


@router.post("/scan")
async def scan_subnet(
    body: DiscoveryScanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    snmp = SNMPEngine()
    engine = DiscoveryEngine(snmp_engine=snmp, session_factory=async_session_factory)
    result = await engine.scan_subnet(body.cidr, body.communities)
    await engine.persist(result)
    return {"result": result}


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID) -> dict:
    raise HTTPException(status_code=404, detail="background jobs not implemented yet")
