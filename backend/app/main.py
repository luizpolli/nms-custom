"""NMS Custom — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import Settings
from app.database import engine, init_db
from app.api.devices import router as devices_router
from app.api.credentials import router as credentials_router
from app.api.performance import router as performance_router
from app.api.mibs import router as mibs_router
from app.api.discovery import router as discovery_router
from app.api.commands import router as commands_router
from app.api.ios import router as ios_router
from app.api.topology import router as topology_router
from app.api.alarms import router as alarms_router
from app.api.reports import router as reports_router
from app.api.health import router as health_router
from app.workers import WorkerSupervisor

settings = Settings()
worker_supervisor: WorkerSupervisor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup & shutdown hooks."""
    global worker_supervisor
    await init_db()
    worker_supervisor = WorkerSupervisor()
    await worker_supervisor.start()
    yield
    if worker_supervisor:
        await worker_supervisor.stop()


app = FastAPI(
    title="NMS Custom",
    description="Network Management System inspired by Cisco Prime",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(devices_router, prefix="/api/devices", tags=["devices"])
app.include_router(credentials_router, prefix="/api/credentials", tags=["credentials"])
app.include_router(performance_router, prefix="/api/performance", tags=["performance"])
app.include_router(mibs_router, prefix="/api/mibs", tags=["mibs"])
app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"])
app.include_router(commands_router, prefix="/api/commands", tags=["commands"])
app.include_router(ios_router, prefix="/api/ios", tags=["ios"])
app.include_router(topology_router, prefix="/api/topology", tags=["topology"])
app.include_router(alarms_router, prefix="/api/alarms", tags=["alarms"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(health_router, prefix="/health", tags=["health"])


@app.get("/api/health")
async def api_health():
    """Simple API health check."""
    return {"status": "ok", "app": "nms-custom"}
