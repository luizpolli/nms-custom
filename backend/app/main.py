"""NMS Custom — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from app.config import Settings
from app.database import engine, init_db
from app.api.devices import router as devices_router
from app.api.credentials import router as credentials_router
from app.api.performance import router as performance_router
from app.api.mibs import router as mibs_router
from app.api.monitoring_policies import router as monitoring_policies_router
from app.api.discovery import router as discovery_router
from app.api.commands import router as commands_router
from app.api.ios import router as ios_router
from app.api.topology import router as topology_router
from app.api.alarms import router as alarms_router
from app.api.alarm_rules import router as alarm_rules_router
from app.api.kpi_thresholds import router as kpi_thresholds_router
from app.api.reports import router as reports_router
from app.api.report_schedules import router as report_schedules_router
from app.api.health import router as health_router
from app.api.settings import router as settings_router
from app.api.system import router as system_router
from app.api.telemetry import router as telemetry_router
from app.api.assurance import router as assurance_router
from app.workers import WorkerSupervisor
from app.security.auth import require_api_auth
from app.security.redaction import configure_log_redaction

settings = Settings()
configure_log_redaction()
worker_supervisor: WorkerSupervisor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup & shutdown hooks."""
    global worker_supervisor
    if settings.app_env == "test":
        yield
        return

    await init_db()
    if settings.start_embedded_workers:
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

if settings.https_redirect_enabled and settings.https_enabled:
    app.add_middleware(HTTPSRedirectMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
_api_auth = [Depends(require_api_auth)]
app.include_router(devices_router, prefix="/api/devices", tags=["devices"], dependencies=_api_auth)
app.include_router(credentials_router, prefix="/api/credentials", tags=["credentials"], dependencies=_api_auth)
app.include_router(performance_router, prefix="/api/performance", tags=["performance"], dependencies=_api_auth)
app.include_router(mibs_router, prefix="/api/mibs", tags=["mibs"], dependencies=_api_auth)
app.include_router(monitoring_policies_router, prefix="/api/monitoring-policies", tags=["monitoring-policies"], dependencies=_api_auth)
app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"], dependencies=_api_auth)
app.include_router(commands_router, prefix="/api/commands", tags=["commands"], dependencies=_api_auth)
app.include_router(ios_router, prefix="/api/ios", tags=["ios"], dependencies=_api_auth)
app.include_router(topology_router, prefix="/api/topology", tags=["topology"], dependencies=_api_auth)
app.include_router(alarms_router, prefix="/api/alarms", tags=["alarms"], dependencies=_api_auth)
app.include_router(alarm_rules_router, prefix="/api/alarm-rules", tags=["alarm-rules"], dependencies=_api_auth)
app.include_router(kpi_thresholds_router, prefix="/api/kpi-thresholds", tags=["kpi-thresholds"], dependencies=_api_auth)
app.include_router(reports_router, prefix="/api/reports", tags=["reports"], dependencies=_api_auth)
app.include_router(report_schedules_router, prefix="/api/report-schedules", tags=["report-schedules"], dependencies=_api_auth)
app.include_router(settings_router, prefix="/api/settings", tags=["settings"], dependencies=_api_auth)
app.include_router(system_router, prefix="/api/system", tags=["system"], dependencies=_api_auth)
app.include_router(telemetry_router, prefix="/api/telemetry", tags=["telemetry"], dependencies=_api_auth)
app.include_router(assurance_router, prefix="/api/assurance", tags=["assurance"], dependencies=_api_auth)
app.include_router(health_router, prefix="/health", tags=["health"])


@app.get("/api/health")
async def api_health():
    """Simple API health check."""
    return {"status": "ok", "app": "nms-custom"}
