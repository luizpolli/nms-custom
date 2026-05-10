"""Pydantic v2 schemas for network discovery."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DiscoveryScanRequest(BaseModel):
    cidr: str
    communities: List[str] = Field(default_factory=lambda: ["public"])


class DiscoveredDeviceRead(BaseModel):
    ip: str
    sys_name: Optional[str] = None
    sys_descr: Optional[str] = None
    vendor: Optional[str] = None
    os_type: Optional[str] = None


class ScanResult(BaseModel):
    discovered: int
    persisted: int
    devices: List[DiscoveredDeviceRead]
