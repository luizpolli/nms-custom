"""NMS Custom — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.ai_ops import router as ai_ops_router
from app.api.alarm_rules import router as alarm_rules_router
from app.api.alarms import router as alarms_router
from app.api.assurance import router as assurance_router
from app.api.bulkstats import router as bulkstats_router
from app.api.command_schedules import router as command_schedules_router
from app.api.commands import router as commands_router
from app.api.credentials import router as credentials_router
from app.api.devices import router as devices_router
from app.api.discovery import router as discovery_router
from app.api.forwarding import router as forwarding_router
from app.api.health import router as health_router
from app.api.ios import router as ios_router
from app.api.kpi_thresholds import router as kpi_thresholds_router
from app.api.lab import router as lab_router
from app.api.metrics import router as metrics_router
from app.api.mibs import router as mibs_router
from app.api.monitoring_policies import router as monitoring_policies_router
from app.api.performance import router as performance_router
from app.api.report_schedules import router as report_schedules_router
from app.api.reports import router as reports_router
from app.api.services import router as services_router
from app.api.settings import router as settings_router
from app.api.system import router as system_router
from app.api.telemetry import router as telemetry_router
from app.api.topology import router as topology_router
from app.config import Settings
from app.database import async_session_factory, init_db
from app.security.auth import principal_from_presented_key, require_api_auth
from app.security.body_size import BodySizeLimitMiddleware
from app.security.rate_limit import RateLimitMiddleware
from app.security.redaction import configure_log_redaction
from app.services.account_audit import record_account_activity
from app.services.observability.metrics import observe_request
from app.workers import WorkerSupervisor

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
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_env == "development" else None,
    redoc_url="/api/redoc" if settings.app_env == "development" else None,
    openapi_url="/api/openapi.json" if settings.app_env == "development" else None,
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
app.middleware("http")(observe_request)


def _audit_excluded_path(path: str) -> bool:
    return (
        path in {"/api/health", "/health/live", "/health/ready", "/metrics"}
        or path.startswith("/api/docs")
        or path.startswith("/api/openapi")
        or path.startswith("/api/settings/account-audit")
    )


@app.middleware("http")
async def account_activity_audit(request, call_next):
    response = await call_next(request)
    if (
        settings.account_audit_enabled
        and settings.app_env != "test"
        and request.url.path.startswith("/api/")
        and not _audit_excluded_path(request.url.path)
    ):
        presented = request.headers.get("x-api-key")
        auth_header = request.headers.get("authorization", "")
        if not presented and auth_header.lower().startswith("bearer "):
            presented = auth_header[7:].strip()
        principal = principal_from_presented_key(presented)
        if response.status_code == 401:
            principal = principal_from_presented_key(None)
        async with async_session_factory() as session:
            await record_account_activity(
                session,
                principal=principal,
                action=f"api.{request.method.lower()}",
                source_ip=request.client.host if request.client else None,
                outcome="success" if response.status_code < 400 else "failure",
                message=f"{request.method} {request.url.path}",
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.url.query),
                    "status_code": response.status_code,
                },
            )
            await session.commit()
    return response

# Rate limit is added before TrustedHost so the limit response still returns
# a fast 429 even for hosts that pass TrustedHost. APP_ENV=test and
# RATE_LIMIT_ENABLED=false short-circuit inside the middleware.
if settings.rate_limit_enabled and settings.app_env != "test":
    app.add_middleware(RateLimitMiddleware)

# Body-size limit middleware is added after rate-limit so limits are checked
# after the request is accepted (not throttled). APP_ENV=test and
# BODY_SIZE_LIMIT_ENABLED=false short-circuit inside the middleware.
if settings.body_size_limit_enabled and settings.app_env != "test":
    app.add_middleware(BodySizeLimitMiddleware)

# Add TrustedHost last so it is the outermost middleware and rejects bad Host
# headers before request metrics or route handling.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

# Include routers
_api_auth = [Depends(require_api_auth)]
app.include_router(devices_router, prefix="/api/devices", tags=["devices"], dependencies=_api_auth)
app.include_router(credentials_router, prefix="/api/credentials", tags=["credentials"], dependencies=_api_auth)
app.include_router(performance_router, prefix="/api/performance", tags=["performance"], dependencies=_api_auth)
app.include_router(mibs_router, prefix="/api/mibs", tags=["mibs"], dependencies=_api_auth)
app.include_router(monitoring_policies_router, prefix="/api/monitoring-policies", tags=["monitoring-policies"], dependencies=_api_auth)
app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"], dependencies=_api_auth)
app.include_router(commands_router, prefix="/api/commands", tags=["commands"], dependencies=_api_auth)
app.include_router(command_schedules_router, prefix="/api/command-schedules", tags=["command-schedules"], dependencies=_api_auth)
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
app.include_router(forwarding_router, prefix="/api/forwarding", tags=["forwarding"], dependencies=_api_auth)
app.include_router(assurance_router, prefix="/api/assurance", tags=["assurance"], dependencies=_api_auth)
app.include_router(ai_ops_router, prefix="/api/ai-ops", tags=["ai-ops"], dependencies=_api_auth)
app.include_router(services_router, prefix="/api/services", tags=["services"], dependencies=_api_auth)
app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(metrics_router, tags=["metrics"])
app.include_router(lab_router, prefix="/api/lab", tags=["lab"], dependencies=_api_auth)
app.include_router(bulkstats_router, prefix="/api/bulkstats", tags=["bulkstats"], dependencies=_api_auth)


@app.get("/api/health")
async def api_health():
    """Simple API health check."""
    return {"status": "ok", "app": "nms-custom"}
