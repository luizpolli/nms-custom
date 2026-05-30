"""Pydantic v2 schemas for network discovery."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiscoveryScanRequest(BaseModel):
    cidr: str
    communities: list[str] = Field(default_factory=lambda: ["public"])


class DiscoveredDeviceRead(BaseModel):
    ip: str
    sys_name: str | None = None
    sys_descr: str | None = None
    vendor: str | None = None
    os_type: str | None = None


class ScanResult(BaseModel):
    discovered: int
    persisted: int
    devices: list[DiscoveredDeviceRead]
