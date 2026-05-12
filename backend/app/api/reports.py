"""Reports API routes."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.database import async_session_factory
from app.security.audit import audit
from app.services.reports.registry import ReportRegistry

router = APIRouter()
_registry = ReportRegistry(async_session_factory)


class ReportInfo(BaseModel):
    name: str
    format: str = "xlsx"
    description: str | None = None


class ReportRequest(BaseModel):
    name: Literal["device_inventory", "kpi", "alarms", "executive_summary", "device_health"]
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def validate_params(cls, params: dict[str, Any]) -> dict[str, Any]:
        forbidden = {"password", "secret", "token", "community", "auth_key", "enc_key"}
        if any(str(k).lower() in forbidden for k in params):
            raise ValueError("Report parameters must not contain secrets")
        return params


@router.get("/available", response_model=list[ReportInfo])
async def list_reports() -> list[ReportInfo]:
    available = _registry.list_available()
    if isinstance(available, list) and available and isinstance(available[0], dict):
        return [ReportInfo(**item) for item in available]
    return [ReportInfo(name=str(item)) for item in available]


@router.post("/generate")
async def generate_report(body: ReportRequest) -> StreamingResponse:
    try:
        content, filename, content_type = await _registry.generate(body.name, body.params)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit("report.generate", target=body.name, params=body.params)
    return StreamingResponse(
        iter([content]),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
