"""Retrieval-grounded AI Ops assistant orchestrator.

Flow:
  question -> validate -> retrieve evidence -> redact -> LLM.complete ->
  validate citations -> return answer + citations.

The orchestrator never lets free text reach the provider without redaction
and never accepts an answer that fails citation validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm
from app.models.kpi import KPI

from .guardrails import (
    EvidenceItem,
    GuardrailLimits,
    ValidatedAnswer,
    redact_text,
    validate_answer,
    validate_question,
)
from .providers import LLMProvider, LLMRequest, NullLLMProvider

_SYSTEM_PROMPT = (
    "Eres un asistente operativo de un NMS. Sólo puedes afirmar lo que esté "
    "respaldado por la evidencia entregada. Cada afirmación material debe "
    "incluir una cita en el formato [citation_id]. Si no hay evidencia "
    "suficiente, responde explícitamente que faltan datos. Nunca inventes "
    "hostnames, IPs ni recomendaciones de cambio de configuración."
)


@dataclass(slots=True)
class AssistantAnswer:
    question: str
    answer: str
    citations: list[EvidenceItem] = field(default_factory=list)
    advisory_only: bool = True
    rejected_reason: str | None = None
    provider: str = "null"


async def _retrieve_alarms(db: AsyncSession, limit: int) -> list[Alarm]:
    stmt = (
        select(Alarm)
        .where(Alarm.state.in_(["active", "acknowledged"]))
        .order_by(Alarm.last_seen.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _retrieve_kpis(db: AsyncSession, hours: int, limit: int) -> list[KPI]:
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 168)))
    stmt = (
        select(KPI)
        .where(KPI.timestamp >= since, KPI.quality != "good")
        .order_by(KPI.timestamp.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


def _build_evidence(alarms: list[Alarm], kpis: list[KPI]) -> list[EvidenceItem]:
    out: list[EvidenceItem] = []
    for a in alarms:
        label = redact_text(a.message or "alarma sin mensaje")
        detail = redact_text(
            f"severity={a.severity} state={a.state} category={a.category}"
        )
        out.append(
            EvidenceItem(
                citation_id=f"alarm:{a.id}",
                source_type="alarm",
                label=label,
                detail=detail,
            )
        )
    for k in kpis:
        name = k.metric_name or k.kpi_type or "kpi"
        out.append(
            EvidenceItem(
                citation_id=f"kpi:{k.id}",
                source_type="kpi",
                label=redact_text(f"{name} value={k.value} quality={k.quality}"),
            )
        )
    return out


def _render_user_prompt(question: str, evidence: list[EvidenceItem]) -> str:
    body = ["Pregunta:", question.strip(), "", "Evidencia disponible:"]
    for e in evidence:
        body.append(f"- [{e.citation_id}] {e.source_type}: {e.label}")
    body.append("")
    body.append(
        "Responde en español usando sólo esta evidencia. Cita cada afirmación "
        "con el formato [citation_id]."
    )
    return "\n".join(body)


async def answer_question(
    db: AsyncSession,
    question: str,
    *,
    provider: LLMProvider | None = None,
    limits: GuardrailLimits | None = None,
    kpi_hours: int = 24,
) -> AssistantAnswer:
    """End-to-end retrieval + guardrails + provider call."""
    limits = limits or GuardrailLimits()
    provider = provider or NullLLMProvider()
    q = validate_question(question, limits)

    alarms = await _retrieve_alarms(db, limits.max_alarms)
    kpis = await _retrieve_kpis(db, kpi_hours, limits.max_kpis)
    evidence = _build_evidence(alarms, kpis)

    redacted_question = redact_text(q)
    user_prompt = _render_user_prompt(redacted_question, evidence)

    raw = await provider.complete(
        LLMRequest(system=_SYSTEM_PROMPT, user=user_prompt, evidence=evidence)
    )
    validated: ValidatedAnswer = validate_answer(raw, evidence, limits)
    cited_items = [e for e in evidence if e.citation_id in set(validated.cited)]
    return AssistantAnswer(
        question=q,
        answer=validated.answer,
        citations=cited_items,
        rejected_reason=validated.rejected_reason,
        provider=getattr(provider, "name", "unknown"),
    )
