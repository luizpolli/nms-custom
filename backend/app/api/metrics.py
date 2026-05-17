"""Prometheus scrape endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.services.observability.metrics import render_prometheus_metrics

router = APIRouter()


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    payload, media_type = await render_prometheus_metrics()
    return Response(content=payload, media_type=media_type)
