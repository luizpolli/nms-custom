"""KPI service — SNMP polling → time-series persistence."""

from __future__ import annotations

from app.services.kpi.engine import KPIEngine
from app.services.kpi.mapper import InterfaceSnapshot, KPIRecord, map_cpu_memory, map_interfaces

__all__ = ["KPIEngine", "KPIRecord", "InterfaceSnapshot", "map_cpu_memory", "map_interfaces"]
