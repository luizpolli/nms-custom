"""AI-assisted operations advisory APIs.

These endpoints are deterministic advisory scaffolding: they summarize and cite
underlying alarms/KPIs/services so an LLM can be plugged in later without making
uncited operational claims.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.alarm import Alarm
from app.models.kpi import KPI
from app.security.auth import require_roles, roles_from_setting
from app.services.ai_ops.assistant import answer_question
from app.services.ai_ops.guardrails import GuardrailLimits
from app.services.ai_ops.providers import get_provider

router = APIRouter()


class AdvisoryCitation(BaseModel):
    source_type: str
    object_id: str
    label: str
    timestamp: datetime | None = None
    detail: str | None = None


class AdvisoryResponse(BaseModel):
    advisory_type: str
    title: str
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    citations: list[AdvisoryCitation] = Field(default_factory=list)
    advisory_only: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


_SEVERITY_RANK = {"critical": 5, "major": 4, "minor": 3, "warning": 2, "info": 1, "clear": 0}
_RUNBOOKS = {
    "link": [
        "Verifica estado físico/óptico del enlace y errores CRC/discards en ambos extremos.",
        "Confirma si hay alarmas espejo en el vecino antes de cambiar configuración.",
    ],
    "device": [
        "Revisa disponibilidad, CPU/memoria y último reboot del equipo.",
        "Valida energía/ambiente antes de asumir falla lógica.",
    ],
    "auth": [
        "Revisa credenciales/perfiles SNMP/SSH y cambios recientes de RBAC.",
        "Confirma que la falla no sea por rotación pendiente de secretos.",
    ],
    "telemetry": [
        "Compara muestras SNMP vs telemetry para descartar problema de collector.",
        "Revisa lag, drops y last_seen del collector/subscription.",
    ],
}


def _worst_alarm(alarms: list[Alarm]) -> Alarm | None:
    if not alarms:
        return None
    return sorted(alarms, key=lambda a: (_SEVERITY_RANK.get((a.severity or "info").lower(), 1), a.last_seen), reverse=True)[0]


def _alarm_citation(alarm: Alarm) -> AdvisoryCitation:
    return AdvisoryCitation(
        source_type="alarm",
        object_id=str(alarm.id),
        label=alarm.message,
        timestamp=alarm.last_seen,
        detail=f"severity={alarm.severity} state={alarm.state} source={alarm.source_host}",
    )


@router.get("/alarm-groups/{group_key}/summary", response_model=AdvisoryResponse)
async def alarm_group_summary(
    group_key: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdvisoryResponse:
    result = await db.execute(select(Alarm).where(Alarm.state.in_(["active", "acknowledged", "suppressed"])).limit(2000))
    alarms = [a for a in result.scalars().all() if (a.correlation_group_id and f"group:{a.correlation_group_id}" == group_key) or a.dedup_key == group_key or a.correlation_key == group_key]
    worst = _worst_alarm(alarms)
    if not worst:
        return AdvisoryResponse(advisory_type="alarm_group_summary", title="Sin datos para el grupo", summary="No encontré alarmas activas/ack/suprimidas con esa llave.")
    impacted = sorted({a.source_host for a in alarms if a.source_host})
    category = worst.category or "other"
    return AdvisoryResponse(
        advisory_type="alarm_group_summary",
        title=f"Grupo {group_key}: {worst.severity} / {category}",
        summary=f"Hay {len(alarms)} alarma(s) relacionadas; peor severidad {worst.severity}. Impacto observado en: {', '.join(impacted) or 'sin host identificado'}.",
        recommendations=_RUNBOOKS.get(category, ["Revisa timeline, topología e interfaces relacionadas antes de ejecutar cambios."]),
        citations=[_alarm_citation(a) for a in alarms[:10]],
    )


@router.get("/kpis/anomalies/explain", response_model=AdvisoryResponse)
async def kpi_anomaly_explanation(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: uuid.UUID | None = None,
    hours: int = 24,
    limit: int = 20,
) -> AdvisoryResponse:
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 168)))
    stmt = select(KPI).where(KPI.timestamp >= since, KPI.quality != "good").order_by(KPI.timestamp.desc()).limit(min(limit, 100))
    if device_id:
        stmt = stmt.where(KPI.device_id == device_id)
    result = await db.execute(stmt)
    kpis = list(result.scalars().all())
    if not kpis:
        return AdvisoryResponse(advisory_type="kpi_anomaly_explanation", title="Sin anomalías KPI recientes", summary="No hay muestras KPI non-good en la ventana solicitada.")
    paths = sorted({k.metric_name or k.kpi_type for k in kpis})
    return AdvisoryResponse(
        advisory_type="kpi_anomaly_explanation",
        title=f"{len(kpis)} anomalía(s) KPI recientes",
        summary=f"Las métricas afectadas incluyen: {', '.join(paths[:8])}. Esto sugiere degradación observable, no causa raíz confirmada.",
        recommendations=[
            "Correlaciona estas muestras con alarmas activas y cambios recientes.",
            "Valida si la anomalía aparece en SNMP y telemetry antes de escalar.",
        ],
        citations=[
            AdvisoryCitation(
                source_type="kpi",
                object_id=str(k.id),
                label=k.metric_name or k.kpi_type,
                timestamp=k.timestamp,
                detail=f"value={k.value} quality={k.quality} device_id={k.device_id}",
            )
            for k in kpis[:10]
        ],
    )


@router.get("/runbooks/suggest", response_model=AdvisoryResponse)
async def runbook_suggestions(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
    limit: int = 10,
) -> AdvisoryResponse:
    stmt = select(Alarm).where(Alarm.state == "active").order_by(Alarm.last_seen.desc()).limit(min(limit, 50))
    if category:
        stmt = stmt.where(Alarm.category == category)
    result = await db.execute(stmt)
    alarms = list(result.scalars().all())
    categories = sorted({a.category for a in alarms if a.category})
    recommendations: list[str] = []
    for cat in categories or ([category] if category else []):
        recommendations.extend(_RUNBOOKS.get(cat or "", []))
    if not recommendations:
        recommendations = ["No hay runbook específico; usa timeline, topología, KPIs y auditoría para acotar causa antes de tocar producción."]
    return AdvisoryResponse(
        advisory_type="runbook_suggestion",
        title="Sugerencias de runbook",
        summary=f"Sugerencias basadas en {len(alarms)} alarma(s) activa(s) y categoría(s): {', '.join(categories) or category or 'general'}.",
        recommendations=list(dict.fromkeys(recommendations)),
        citations=[_alarm_citation(a) for a in alarms[:10]],
    )


@router.get("/reports/narrative", response_model=AdvisoryResponse)
async def report_narrative(db: Annotated[AsyncSession, Depends(get_db)], hours: int = 24) -> AdvisoryResponse:
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 168)))
    alarms = list((await db.execute(select(Alarm).where(Alarm.last_seen >= since).order_by(Alarm.last_seen.desc()).limit(50))).scalars().all())
    kpis = list((await db.execute(select(KPI).where(KPI.timestamp >= since, KPI.quality != "good").order_by(KPI.timestamp.desc()).limit(50))).scalars().all())
    worst = _worst_alarm(alarms)
    title = "Narrativa operacional"
    summary = f"En las últimas {hours}h: {len(alarms)} alarma(s) y {len(kpis)} KPI(s) non-good."
    if worst:
        summary += f" Peor alarma: {worst.severity} en {worst.source_host}: {worst.message}."
    return AdvisoryResponse(
        advisory_type="report_narrative",
        title=title,
        summary=summary,
        recommendations=["Usa esta narrativa como borrador; confirma con datos crudos antes de enviarla a clientes."],
        citations=[_alarm_citation(a) for a in alarms[:5]] + [
            AdvisoryCitation(source_type="kpi", object_id=str(k.id), label=k.metric_name or k.kpi_type, timestamp=k.timestamp, detail=f"quality={k.quality} value={k.value}")
            for k in kpis[:5]
        ],
    )


class AssistantAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    kpi_hours: int = Field(default=24, ge=1, le=168)


class AssistantAnswerResponse(BaseModel):
    question: str
    answer: str
    citations: list[AdvisoryCitation] = Field(default_factory=list)
    provider: str
    advisory_only: bool = True
    rejected_reason: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


_ASSISTANT_ROLES = roles_from_setting(
    getattr(settings, "ai_ops_assistant_allowed_roles", "admin,ai-ops")
)


@router.post(
    "/assistant/ask",
    response_model=AssistantAnswerResponse,
    dependencies=[Depends(require_roles(*_ASSISTANT_ROLES))],
)
async def assistant_ask(
    payload: AssistantAskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssistantAnswerResponse:
    if not getattr(settings, "ai_ops_llm_enabled", False):
        raise HTTPException(status_code=503, detail="AI Ops LLM assistant disabled")
    provider = get_provider(getattr(settings, "ai_ops_llm_provider", "null"))
    limits = GuardrailLimits(
        max_alarms=getattr(settings, "ai_ops_max_alarms", 20),
        max_kpis=getattr(settings, "ai_ops_max_kpis", 20),
        max_question_chars=getattr(settings, "ai_ops_max_question_chars", 1000),
        max_answer_chars=getattr(settings, "ai_ops_max_answer_chars", 2000),
    )
    try:
        result = await answer_question(
            db, payload.question, provider=provider, limits=limits, kpi_hours=payload.kpi_hours
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AssistantAnswerResponse(
        question=result.question,
        answer=result.answer,
        citations=[
            AdvisoryCitation(
                source_type=c.source_type,
                object_id=c.citation_id,
                label=c.label,
                detail=c.detail or None,
            )
            for c in result.citations
        ],
        provider=result.provider,
        rejected_reason=result.rejected_reason,
    )
