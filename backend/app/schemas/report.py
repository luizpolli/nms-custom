"""Pydantic v2 schemas for report API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportInfo(BaseModel):
    name: str
    format: str
    description: str


class ReportRequest(BaseModel):
    name: str
    params: dict = Field(default_factory=dict)
