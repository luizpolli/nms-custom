"""KPI service — SNMP polling → time-series persistence."""

from __future__ import annotations

from app.services.kpi.mapper import KPIRecord, InterfaceSnapshot, map_cpu_memory, map_interfaces
from app.services.kpi.engine import KPIEngine

__all__ = ["KPIEngine", "KPIRecord", "InterfaceSnapshot", "map_cpu_memory", "map_interfaces"]
