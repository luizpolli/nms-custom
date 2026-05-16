"""Report registry — central entry point for all NMS reports."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reports.excel import ExcelReporter
from app.services.reports.pdf import PDFReporter
from app.security.redaction import redact

_REPORTS = [
    {"name": "device_inventory", "format": "xlsx", "description": "Device, inventory and IOS version details"},
    {"name": "kpi", "format": "xlsx", "description": "KPI time-series by device and metric"},
    {"name": "alarms", "format": "xlsx", "description": "Alarm detail and severity summary"},
    {"name": "monitoring_policies", "format": "xlsx", "description": "Monitoring policy configuration, cadence and execution status"},
    {"name": "executive_summary", "format": "pdf", "description": "Executive summary with alarm and KPI overview"},
    {"name": "device_health", "format": "pdf", "description": "Per-device health: interfaces, alarms, CPU/mem trend"},
]

_CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


class ReportRegistry:
    """Central registry that delegates report generation to ExcelReporter / PDFReporter."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._excel = ExcelReporter(session_factory)
        self._pdf = PDFReporter(session_factory)

    def list_available(self) -> list[dict]:
        """Return metadata for all available reports."""
        return list(_REPORTS)

    async def generate(self, name: str, params: dict) -> tuple[bytes, str, str]:
        """Generate a report by name and return (bytes, filename, content_type).

        Raises:
            KeyError: If *name* is not a known report.
        """
        report_meta = next((r for r in _REPORTS if r["name"] == name), None)
        if report_meta is None:
            raise KeyError(f"Unknown report: {name!r}")

        fmt = report_meta["format"]
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"nms-{name}-{ts}.{fmt}"
        content_type = _CONTENT_TYPES[fmt]

        logger.info("ReportRegistry.generate: name={} params={}", name, redact(params))
        content = await self._dispatch(name, params)
        return content, filename, content_type

    async def _dispatch(self, name: str, params: dict) -> bytes:
        if name == "device_inventory":
            return await self._excel.device_inventory_report()
        if name == "kpi":
            return await self._excel.kpi_report(
                since=params["since"], until=params["until"],
                device_ids=params.get("device_ids"),
            )
        if name == "alarms":
            return await self._excel.alarm_report(since=params["since"], until=params["until"])
        if name == "monitoring_policies":
            return await self._excel.monitoring_policy_report()
        if name == "executive_summary":
            return await self._pdf.executive_summary(since=params["since"], until=params["until"])
        if name == "device_health":
            return await self._pdf.device_health_report(device_id=params["device_id"])
        raise KeyError(name)  # unreachable, guarded in generate()
