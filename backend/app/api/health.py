"""Health check API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/")
async def health_root() -> dict:
    return {"status": "ok"}


@router.get("/live")
async def health_live() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def health_ready(db: Annotated[AsyncSession, Depends(get_db)]) -> JSONResponse:
    errors: list[str] = []

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        errors.append(f"db: {exc}")

    try:
        import redis.asyncio as aioredis

        from app.config import Settings
        settings = Settings()
        r = aioredis.from_url(settings.redis_url, socket_timeout=2)
        await r.ping()
        await r.aclose()
    except ImportError:
        pass  # redis.asyncio not installed; skip
    except Exception as exc:
        errors.append(f"redis: {exc}")

    if errors:
        return JSONResponse(status_code=503, content={"ok": False, "errors": errors})
    return JSONResponse(status_code=200, content={"ok": True})
