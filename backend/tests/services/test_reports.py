"""Smoke tests for ExcelReporter, PDFReporter, and ReportRegistry."""

from __future__ import annotations

import pytest

from app.services.reports.excel import ExcelReporter
from app.services.reports.pdf import PDFReporter
from app.services.reports.registry import ReportRegistry


def test_excel_reporter_instantiates() -> None:
    reporter = ExcelReporter(None)  # type: ignore[arg-type]
    assert reporter is not None


def test_pdf_reporter_instantiates() -> None:
    reporter = PDFReporter(None)  # type: ignore[arg-type]
    assert reporter is not None


def test_registry_list_available_has_required_fields() -> None:
    registry = ReportRegistry(None)  # type: ignore[arg-type]
    for entry in registry.list_available():
        assert "name" in entry
        assert "format" in entry
        assert "description" in entry


def test_registry_list_available_names() -> None:
    registry = ReportRegistry(None)  # type: ignore[arg-type]
    names = {r["name"] for r in registry.list_available()}
    assert names == {
        "device_inventory",
        "kpi",
        "kpi_top_n",
        "kpi_trends",
        "baseline_comparison",
        "tca",
        "alarms",
        "monitoring_policies",
        "assurance_trend",
        "service_trend",
        "executive_summary",
        "device_health",
    }


def test_registry_list_available_formats() -> None:
    registry = ReportRegistry(None)  # type: ignore[arg-type]
    for entry in registry.list_available():
        assert entry["format"] in {"xlsx", "pdf"}


@pytest.mark.asyncio
async def test_registry_generate_unknown_name_raises_key_error() -> None:
    registry = ReportRegistry(None)  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        await registry.generate("nonexistent_report", {})
