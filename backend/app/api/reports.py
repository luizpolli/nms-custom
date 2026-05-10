"""Reports API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import async_session_factory
from app.services.reports.registry import ReportRegistry

router = APIRouter()
_registry = ReportRegistry(async_session_factory)


class ReportInfo(BaseModel):
    name: str
    format: str = "xlsx"
    description: str | None = None


class ReportRequest(BaseModel):
    name: str
    params: dict[str, Any] = {}


@router.get("/available", response_model=list[ReportInfo])
async def list_reports() -> list[ReportInfo]:
    available = _registry.list_available()
    if isinstance(available, list) and available and isinstance(available[0], dict):
        return [ReportInfo(**item) for item in available]
    return [ReportInfo(name=str(item)) for item in available]


@router.post("/generate")
async def generate_report(body: ReportRequest) -> StreamingResponse:
    content, filename, content_type = await _registry.generate(body.name, body.params)
    return StreamingResponse(
        iter([content]),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
