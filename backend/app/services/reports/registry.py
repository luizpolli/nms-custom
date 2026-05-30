"""Report registry — central entry point for all NMS reports."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.redaction import redact
from app.services.reports.excel import ExcelReporter
from app.services.reports.pdf import PDFReporter

_REPORTS = [
    {"name": "device_inventory", "format": "xlsx", "description": "Device, inventory and IOS version details"},
    {"name": "kpi", "format": "xlsx", "description": "KPI time-series with Cricket-style bucket + consolidation (avg/min/max/p95)"},
    {"name": "kpi_top_n", "format": "xlsx", "description": "PPM-style Top-N devices by KPI with p95/p99 ranking"},
    {"name": "kpi_trends", "format": "xlsx", "description": "Cricket-style hourly / daily / weekly trend summary per device"},
    {"name": "baseline_comparison", "format": "xlsx", "description": "PPM-style baseline comparison: current period vs prior windows"},
    {"name": "tca", "format": "xlsx", "description": "Threshold Crossing Alerts: definitions and crossings in period"},
    {"name": "alarms", "format": "xlsx", "description": "Alarm detail and severity summary"},
    {"name": "monitoring_policies", "format": "xlsx", "description": "Monitoring policy configuration, cadence and execution status"},
    {"name": "assurance_trend", "format": "xlsx", "description": "Network assurance score trend bucketed over a time window"},
    {"name": "service_trend", "format": "xlsx", "description": "Per-service score trend with raw snapshots and summary index"},
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
                bucket=params.get("bucket", "raw"),
                consolidation=params.get("consolidation", "avg"),
            )
        if name == "kpi_top_n":
            return await self._excel.kpi_top_n_report(
                since=params["since"], until=params["until"],
                top_n=int(params.get("top_n", 10)),
                consolidation=params.get("consolidation", "p95"),
                kpi_types=params.get("kpi_types"),
            )
        if name == "kpi_trends":
            return await self._excel.kpi_trends_report(
                since=params["since"], until=params["until"],
                device_ids=params.get("device_ids"),
                buckets=params.get("buckets"),
            )
        if name == "baseline_comparison":
            return await self._excel.baseline_comparison_report(
                since=params["since"], until=params["until"],
                baseline_periods=int(params.get("baseline_periods", 4)),
                device_ids=params.get("device_ids"),
            )
        if name == "tca":
            return await self._excel.tca_report(since=params["since"], until=params["until"])
        if name == "alarms":
            return await self._excel.alarm_report(since=params["since"], until=params["until"])
        if name == "monitoring_policies":
            return await self._excel.monitoring_policy_report()
        if name == "assurance_trend":
            return await self._excel.assurance_trend_report(
                since=params["since"], until=params["until"],
                bucket_minutes=int(params.get("bucket_minutes", 15)),
            )
        if name == "service_trend":
            return await self._excel.service_trend_report(
                since=params["since"], until=params["until"],
                service_ids=params.get("service_ids"),
            )
        if name == "executive_summary":
            return await self._pdf.executive_summary(since=params["since"], until=params["until"])
        if name == "device_health":
            return await self._pdf.device_health_report(device_id=params["device_id"])
        raise KeyError(name)  # unreachable, guarded in generate()
