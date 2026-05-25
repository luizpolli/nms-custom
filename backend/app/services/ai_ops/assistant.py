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
    "You are an operational assistant for an NMS. You may only state what is "
    "supported by the provided evidence. Every material claim must include a "
    "citation in [citation_id] format. If there is not enough evidence, state "
    "explicitly that data is missing. Never invent hostnames, IPs, or "
    "configuration-change recommendations."
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
        label = redact_text(a.message or "alarm without message")
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
    body = ["Question:", question.strip(), "", "Available evidence:"]
    for e in evidence:
        body.append(f"- [{e.citation_id}] {e.source_type}: {e.label}")
    body.append("")
    body.append(
        "Answer in English using only this evidence. Cite every material claim "
        "with [citation_id] format."
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
