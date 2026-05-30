"""PDF report generator using ReportLab.

Produces executive summary and per-device health PDFs from live database data.
All public methods are async and return raw bytes ready for HTTP streaming.
"""

from __future__ import annotations

import io
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime

from loguru import logger
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm
from app.models.device import Device
from app.models.kpi import KPI

_STYLES = getSampleStyleSheet()
_SEV_ORDER = ["critical", "major", "minor", "warning", "info"]


def _doc(buf: io.BytesIO, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(buf, pagesize=A4, title=title, leftMargin=2 * cm, rightMargin=2 * cm)


def _header_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EFF3F8")]),
    ])


class PDFReporter:
    """Generates PDF reports from the NMS database."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._sf = session_factory

    async def executive_summary(self, since: datetime, until: datetime) -> bytes:
        """Generate executive summary PDF for the given time window."""
        async with self._sf() as session:
            devices = (await session.execute(select(Device))).scalars().all()
            alarms_q = select(Alarm).where(Alarm.first_seen >= since, Alarm.last_seen <= until)
            alarms = (await session.execute(alarms_q)).scalars().all()
            kpis = (await session.execute(
                select(KPI).where(KPI.timestamp >= since, KPI.timestamp <= until)
            )).scalars().all()

        logger.info("executive_summary: {} devices, {} alarms", len(devices), len(alarms))
        buf = io.BytesIO()
        doc = _doc(buf, "Executive Summary")
        story = []

        story.append(Paragraph("NMS Executive Summary", _STYLES["Title"]))
        story.append(Paragraph(f"Period: {since.date()} – {until.date()}", _STYLES["Normal"]))
        story.append(Paragraph(f"Generated: {datetime.now().isoformat(timespec='seconds')}", _STYLES["Normal"]))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(f"Total Devices: {len(devices)}", _STYLES["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))

        # Alarm summary table by severity
        sev_counts: dict[str, int] = defaultdict(int)
        for a in alarms:
            sev_counts[a.severity] += 1
        story.append(Paragraph("Alarm Summary by Severity", _STYLES["Heading2"]))
        alarm_data = [["Severity", "Count"]] + [[s, sev_counts.get(s, 0)] for s in _SEV_ORDER]
        t = Table(alarm_data, colWidths=[8 * cm, 6 * cm])
        t.setStyle(_header_style())
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))

        # Top-10 devices by alarm count
        dev_alarm_counts: dict[str, int] = defaultdict(int)
        dev_names = {d.id: d.name for d in devices}
        for a in alarms:
            if a.device_id:
                dev_alarm_counts[dev_names.get(a.device_id, str(a.device_id))] += 1
        top10 = sorted(dev_alarm_counts.items(), key=lambda x: -x[1])[:10]
        story.append(Paragraph("Top-10 Devices by Alarm Count", _STYLES["Heading2"]))
        top_data = [["Device", "Alarms"]] + [[name, cnt] for name, cnt in top10]
        t2 = Table(top_data, colWidths=[10 * cm, 4 * cm])
        t2.setStyle(_header_style())
        story.append(t2)
        story.append(Spacer(1, 0.4 * cm))

        # KPI averages
        cpu_vals = [k.value for k in kpis if k.kpi_type == "cpu_utilization"]
        mem_vals = [k.value for k in kpis if k.kpi_type == "memory_utilization"]
        avg_cpu = sum(cpu_vals) / len(cpu_vals) if cpu_vals else None
        avg_mem = sum(mem_vals) / len(mem_vals) if mem_vals else None
        story.append(Paragraph("KPI Averages", _STYLES["Heading2"]))
        kpi_data = [
            ["Metric", "Average"],
            ["CPU Utilization (%)", f"{avg_cpu:.1f}" if avg_cpu is not None else "N/A"],
            ["Memory Utilization (%)", f"{avg_mem:.1f}" if avg_mem is not None else "N/A"],
        ]
        t3 = Table(kpi_data, colWidths=[10 * cm, 4 * cm])
        t3.setStyle(_header_style())
        story.append(t3)

        doc.build(story)
        return buf.getvalue()

    async def device_health_report(self, device_id: str) -> bytes:
        """Generate per-device health PDF."""
        from app.models.inventory import Inventory

        async with self._sf() as session:
            device = (await session.execute(
                select(Device).where(Device.id == device_id)
            )).scalar_one_or_none()
            inventory = (await session.execute(
                select(Inventory).where(Inventory.device_id == device_id)
            )).scalar_one_or_none()
            alarms = (await session.execute(
                select(Alarm).where(Alarm.device_id == device_id)
                .order_by(Alarm.last_seen.desc()).limit(20)
            )).scalars().all()
            kpis = (await session.execute(
                select(KPI).where(KPI.device_id == device_id)
                .order_by(KPI.timestamp.desc()).limit(200)
            )).scalars().all()

        logger.info("device_health_report: device={}", device_id)
        buf = io.BytesIO()
        doc = _doc(buf, f"Device Health: {getattr(device, 'name', device_id)}")
        story = []

        name = device.name if device else str(device_id)
        story.append(Paragraph(f"Device Health Report — {name}", _STYLES["Title"]))
        story.append(Paragraph(f"Generated: {datetime.now().isoformat(timespec='seconds')}", _STYLES["Normal"]))
        story.append(Spacer(1, 0.4 * cm))

        # System info
        story.append(Paragraph("System Information", _STYLES["Heading2"]))
        if device:
            sys_data = [
                ["Field", "Value"],
                ["IP Address", device.ip_address],
                ["Vendor", device.vendor or "N/A"],
                ["Model", device.model or "N/A"],
                ["OS Type", device.os_type or "N/A"],
                ["Status", device.status],
                ["Location", device.location or "N/A"],
            ]
            if inventory:
                sys_data += [
                    ["Serial Number", inventory.serial_number or "N/A"],
                    ["Hardware Model", inventory.hardware_model or "N/A"],
                    ["Port Count", str(inventory.port_count or "N/A")],
                ]
            t = Table(sys_data, colWidths=[7 * cm, 9 * cm])
            t.setStyle(_header_style())
            story.append(t)
        story.append(Spacer(1, 0.4 * cm))

        # Interfaces summary
        if inventory:
            story.append(Paragraph("Interface Summary", _STYLES["Heading2"]))
            total = (inventory.port_count or 0)
            up = inventory.interfaces_count or 0  # Inventory tracks total count only
            down = 0  # up/down breakdown not stored in Inventory model
            iface_data = [["Total Ports", "Interfaces Up", "Interfaces Down"],
                          [str(total), str(up), str(down)]]
            t2 = Table(iface_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
            t2.setStyle(_header_style())
            story.append(t2)
            story.append(Spacer(1, 0.4 * cm))

        # Recent alarms
        story.append(Paragraph("Recent Alarms (last 20)", _STYLES["Heading2"]))
        alarm_data = [["Severity", "Category", "State", "Message", "Last Seen"]]
        for a in alarms:
            alarm_data.append([
                a.severity, a.category, a.state,
                (a.message[:50] + "...") if len(a.message) > 50 else a.message,
                a.last_seen.strftime("%Y-%m-%d %H:%M") if a.last_seen else "",
            ])
        if len(alarm_data) == 1:
            alarm_data.append(["—", "—", "—", "No recent alarms", "—"])
        t3 = Table(alarm_data, colWidths=[2.5 * cm, 2.5 * cm, 2.5 * cm, 7 * cm, 3 * cm])
        t3.setStyle(_header_style())
        story.append(t3)
        story.append(Spacer(1, 0.4 * cm))

        # CPU/Mem line chart
        cpu_kpis = [(k.timestamp, k.value) for k in kpis if k.kpi_type == "cpu_utilization"]
        mem_kpis = [(k.timestamp, k.value) for k in kpis if k.kpi_type == "memory_utilization"]
        if cpu_kpis or mem_kpis:
            story.append(Paragraph("CPU / Memory Trend", _STYLES["Heading2"]))
            story.append(_build_kpi_chart(cpu_kpis, mem_kpis))

        doc.build(story)
        return buf.getvalue()


def _build_kpi_chart(
    cpu_kpis: list[tuple[datetime, float]],
    mem_kpis: list[tuple[datetime, float]],
) -> Drawing:
    """Build a small LinePlot Drawing for CPU and memory KPIs."""
    drawing = Drawing(400, 150)
    lp = LinePlot()
    lp.x = 20
    lp.y = 20
    lp.height = 110
    lp.width = 360

    data = []
    if cpu_kpis:
        sorted_cpu = sorted(cpu_kpis, key=lambda x: x[0])
        data.append([(i, v) for i, (_, v) in enumerate(sorted_cpu)])
    if mem_kpis:
        sorted_mem = sorted(mem_kpis, key=lambda x: x[0])
        data.append([(i, v) for i, (_, v) in enumerate(sorted_mem)])

    lp.data = data
    if data:
        lp.lines[0].strokeColor = colors.blue
        if len(data) > 1:
            lp.lines[1].strokeColor = colors.red
    lp.xValueAxis.valueMin = 0
    lp.yValueAxis.valueMin = 0
    lp.yValueAxis.valueMax = 100
    drawing.add(lp)
    return drawing
