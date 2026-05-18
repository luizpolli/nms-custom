"""Provider-agnostic LLM client interface for AI Ops.

The default `NullLLMProvider` is deterministic and does not call any external
service. Real provider adapters (Anthropic, OpenAI, vLLM, Bedrock, ...) must
implement `LLMProvider.complete` and respect the redacted prompt contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .guardrails import EvidenceItem


@dataclass(frozen=True, slots=True)
class LLMRequest:
    system: str
    user: str
    evidence: list[EvidenceItem]
    max_tokens: int = 512
    temperature: float = 0.0


class LLMProvider(Protocol):
    name: str

    async def complete(self, request: LLMRequest) -> str:
        """Return a single completion string for the request."""
        ...


class NullLLMProvider:
    """Deterministic provider used for tests, lab, and air-gapped deploys.

    Builds a citation-rich summary directly from the evidence so the rest of
    the pipeline (guardrails, API, UI) can be exercised end-to-end without an
    LLM dependency.
    """

    name = "null"

    async def complete(self, request: LLMRequest) -> str:
        if not request.evidence:
            return "No tengo evidencia suficiente para responder con citas."
        lines = [
            f"Resumen determinístico para: {request.user.strip()[:160]}",
            "",
            "Hallazgos:",
        ]
        for item in request.evidence[:10]:
            lines.append(f"- {item.source_type}: {item.label} [{item.citation_id}]")
        lines.append("")
        lines.append(
            "Recomendación: revisa los elementos citados antes de actuar; este "
            "resumen es advisory y no confirma causa raíz."
        )
        return "\n".join(lines)


def get_provider(name: str | None) -> LLMProvider:
    """Return a provider by name. Only `null` ships in-tree."""
    key = (name or "null").strip().lower()
    if key in ("", "null", "none", "off", "disabled"):
        return NullLLMProvider()
    raise ValueError(
        f"unknown ai_ops provider '{name}'. Implement LLMProvider and register it."
    )
