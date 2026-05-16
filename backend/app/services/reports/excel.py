"""Excel report generator using openpyxl.

Produces multi-sheet XLSX workbooks from live database data.
All public methods are async and return raw bytes ready for HTTP streaming.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Callable, Sequence
from collections import defaultdict

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.inventory import Inventory
from app.models.ios_version import IOSVersion
from app.models.kpi import KPI
from app.models.alarm import Alarm
from app.models.monitoring_policy import MonitoringPolicy

_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT = Font(bold=True, color="FFFFFF")


def _style_header_row(ws: Worksheet) -> None:
    """Bold + blue header row, freeze top row."""
    for cell in ws[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"


def _autosize(ws: Worksheet) -> None:
    """Set column width to max content length (capped at 60)."""
    for col_idx, col_cells in enumerate(ws.columns, start=1):
        max_len = max((len(str(c.value or "")) for c in col_cells), default=8)
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 60)


def _finalise(ws: Worksheet) -> None:
    _style_header_row(ws)
    _autosize(ws)


def _wb_to_bytes(wb: openpyxl.Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class ExcelReporter:
    """Generates XLSX reports from the NMS database."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Device inventory report
    # ------------------------------------------------------------------

    async def device_inventory_report(self) -> bytes:
        """Three-sheet workbook: Devices, Inventory, IOS Versions."""
        async with self._sf() as session:
            devices = (await session.execute(select(Device))).scalars().all()
            inventories = (await session.execute(select(Inventory))).scalars().all()
            ios_versions = (await session.execute(select(IOSVersion))).scalars().all()

        logger.info("device_inventory_report: {} devices", len(devices))
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # type: ignore[arg-type]

        self._sheet_devices(wb, devices)
        self._sheet_inventory(wb, inventories, {d.id: d.name for d in devices})
        self._sheet_ios_versions(wb, ios_versions, {d.id: d.name for d in devices})

        return _wb_to_bytes(wb)

    def _sheet_devices(self, wb: openpyxl.Workbook, devices: Sequence[Device]) -> None:
        ws = wb.create_sheet("Devices")
        ws.append(["ID", "Name", "IP Address", "Vendor", "Model", "OS Type", "Status", "Location"])
        for d in devices:
            ws.append([str(d.id), d.name, d.ip_address, d.vendor, d.model, d.os_type, d.status, d.location])
        _finalise(ws)

    def _sheet_inventory(
        self, wb: openpyxl.Workbook, rows: Sequence[Inventory], device_names: dict
    ) -> None:
        ws = wb.create_sheet("Inventory")
        ws.append(["Device", "Serial", "HW Model", "FW Version", "Port Count", "Uptime (s)", "Mem Total", "Mem Free"])
        for inv in rows:
            ws.append([
                device_names.get(inv.device_id, str(inv.device_id)),
                inv.serial_number, inv.hardware_model, inv.firmware_version,
                inv.port_count, inv.uptime_seconds, inv.memory_total, inv.memory_free,
            ])
        _finalise(ws)

    def _sheet_ios_versions(
        self, wb: openpyxl.Workbook, rows: Sequence[IOSVersion], device_names: dict
    ) -> None:
        ws = wb.create_sheet("IOS Versions")
        ws.append(["Device", "Version", "Image File", "Platform", "Is EOL", "Is EOS"])
        for iv in rows:
            ws.append([
                device_names.get(iv.device_id, str(iv.device_id)),
                iv.version, iv.image_file, iv.platform, iv.is_eol, iv.is_eos,
            ])
        _finalise(ws)

    # ------------------------------------------------------------------
    # KPI report
    # ------------------------------------------------------------------

    async def kpi_report(
        self,
        since: datetime,
        until: datetime,
        device_ids: list | None = None,
    ) -> bytes:
        """One sheet per kpi_type; columns = devices, rows = timestamps."""
        async with self._sf() as session:
            q = select(KPI).where(KPI.timestamp >= since, KPI.timestamp <= until)
            if device_ids:
                q = q.where(KPI.device_id.in_(device_ids))
            kpis = (await session.execute(q)).scalars().all()
            devices = (await session.execute(select(Device))).scalars().all()

        device_names = {d.id: d.name for d in devices}
        logger.info("kpi_report: {} rows in [{}, {}]", len(kpis), since, until)

        # Group: kpi_type → {device_id → {timestamp → value}}
        grouped: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
        for kpi in kpis:
            ts = kpi.timestamp.isoformat()
            dev = device_names.get(kpi.device_id, str(kpi.device_id))
            grouped[kpi.kpi_type][dev][ts] = kpi.value

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # type: ignore[arg-type]

        for kpi_type, dev_map in sorted(grouped.items()):
            ws = wb.create_sheet(kpi_type[:31])  # sheet name limit
            all_devs = sorted(dev_map.keys())
            all_ts = sorted({ts for d in dev_map.values() for ts in d})
            ws.append(["Timestamp"] + all_devs)
            for ts in all_ts:
                ws.append([ts] + [dev_map[dev].get(ts) for dev in all_devs])
            _finalise(ws)

        if not wb.sheetnames:
            wb.create_sheet("No Data")

        return _wb_to_bytes(wb)

    # ------------------------------------------------------------------
    # Alarm report
    # ------------------------------------------------------------------

    async def alarm_report(self, since: datetime, until: datetime) -> bytes:
        """Two sheets: Alarms detail and Summary by severity."""
        async with self._sf() as session:
            q = select(Alarm).where(Alarm.first_seen >= since, Alarm.last_seen <= until)
            alarms = (await session.execute(q)).scalars().all()

        logger.info("alarm_report: {} alarms in [{}, {}]", len(alarms), since, until)
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # type: ignore[arg-type]

        self._sheet_alarms(wb, alarms)
        self._sheet_alarm_summary(wb, alarms)
        return _wb_to_bytes(wb)

    def _sheet_alarms(self, wb: openpyxl.Workbook, alarms: Sequence[Alarm]) -> None:
        ws = wb.create_sheet("Alarms")
        ws.append([
            "ID", "Source Host", "Severity", "Category", "State",
            "Event Type", "Message", "First Seen", "Last Seen", "Occurrences",
        ])
        for a in alarms:
            ws.append([
                str(a.id), a.source_host, a.severity, a.category, a.state,
                a.event_type, a.message,
                a.first_seen.isoformat() if a.first_seen else None,
                a.last_seen.isoformat() if a.last_seen else None,
                a.occurrence_count,
            ])
        _finalise(ws)

    def _sheet_alarm_summary(self, wb: openpyxl.Workbook, alarms: Sequence[Alarm]) -> None:
        ws = wb.create_sheet("Summary")
        counts: dict[str, int] = defaultdict(int)
        for a in alarms:
            counts[a.severity] += 1
        ws.append(["Severity", "Count"])
        for severity, count in sorted(counts.items()):
            ws.append([severity, count])
        _finalise(ws)

    # ------------------------------------------------------------------
    # Monitoring policy report
    # ------------------------------------------------------------------

    async def monitoring_policy_report(self) -> bytes:
        """Monitoring policy configuration and execution status."""
        async with self._sf() as session:
            policies = (await session.execute(select(MonitoringPolicy).order_by(MonitoringPolicy.interval_seconds.asc()))).scalars().all()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Monitoring Policies"
        ws.append([
            "Name", "Type", "Enabled", "Interval", "Target", "Custom OIDs",
            "Last Run", "Next Run", "Last Status", "Last Error", "Description",
        ])
        for policy in policies:
            ws.append([
                policy.name,
                policy.policy_type,
                policy.enabled,
                _format_interval(policy.interval_seconds),
                "All devices" if policy.target_all_devices else f"{len(policy.device_ids)} selected devices",
                len(policy.metric_oids or []),
                policy.last_run_at.isoformat() if policy.last_run_at else None,
                policy.next_run_at.isoformat() if policy.next_run_at else None,
                policy.last_status,
                policy.last_error,
                policy.description,
            ])
        _finalise(ws)
        return _wb_to_bytes(wb)


def _format_interval(seconds: int) -> str:
    mapping = {
        60: "1 minute",
        300: "5 minutes",
        900: "15 minutes",
        3600: "1 hour",
        21600: "6 hours",
        43200: "12 hours",
        86400: "24 hours",
    }
    return mapping.get(seconds, f"{seconds}s")
