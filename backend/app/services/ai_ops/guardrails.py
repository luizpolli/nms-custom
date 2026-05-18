"""Guardrails for the AI Ops assistant.

Three responsibilities:
  1. Redact sensitive material (IPs, hostnames, secrets) from any text that
     would leave the trust boundary toward an LLM provider.
  2. Enforce that every generated claim cites at least one retrieved
     evidence item — answers without citations are rejected.
  3. Cap retrieval scope so prompts cannot be inflated past safe limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Conservative patterns; over-redact is safer than leak.
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{1,4}\b")
_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_FQDN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.){2,}[a-zA-Z]{2,}\b")
_SECRET_KEYS = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|bearer|authorization)\s*[:=]\s*\S+"
)
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----"
)
_SNMP_COMMUNITY = re.compile(r"(?i)\bcommunity\s+\S+")


def redact_text(text: str) -> str:
    """Apply all redaction patterns to text before LLM submission."""
    if not text:
        return text
    out = _PRIVATE_KEY_BLOCK.sub("[REDACTED_PRIVATE_KEY]", text)
    out = _SECRET_KEYS.sub(lambda m: f"{m.group(1)}=[REDACTED]", out)
    out = _SNMP_COMMUNITY.sub("community [REDACTED]", out)
    out = _MAC.sub("[REDACTED_MAC]", out)
    out = _IPV4.sub("[REDACTED_IP]", out)
    out = _IPV6.sub("[REDACTED_IP6]", out)
    out = _FQDN.sub("[REDACTED_FQDN]", out)
    return out


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One retrieved fact the LLM is allowed to cite."""

    citation_id: str
    source_type: str  # alarm | kpi | service | runbook
    label: str
    detail: str = ""


@dataclass(slots=True)
class GuardrailLimits:
    max_alarms: int = 20
    max_kpis: int = 20
    max_question_chars: int = 1000
    max_answer_chars: int = 2000
    require_citations: bool = True


@dataclass(slots=True)
class ValidatedAnswer:
    answer: str
    cited: list[str] = field(default_factory=list)
    rejected_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.rejected_reason is None


# Citation IDs always use a `prefix:value` shape (alarm:1, kpi:2, runbook:link).
# Requiring the colon prevents redaction placeholders like [REDACTED_IP] from
# being mistaken for citations.
_CITATION_TAG = re.compile(r"\[([a-zA-Z][a-zA-Z0-9_\-.]*:[a-zA-Z0-9_\-.]+)\]")


def extract_citations(text: str) -> list[str]:
    """Pull `[citation_id]` tokens out of an LLM answer."""
    return _CITATION_TAG.findall(text or "")


def validate_answer(
    answer: str,
    evidence: list[EvidenceItem],
    limits: GuardrailLimits,
) -> ValidatedAnswer:
    """Reject answers that exceed length or fail citation requirements."""
    if not answer or not answer.strip():
        return ValidatedAnswer(answer="", rejected_reason="empty answer")
    if len(answer) > limits.max_answer_chars:
        return ValidatedAnswer(
            answer=answer[: limits.max_answer_chars],
            rejected_reason="answer exceeded max length",
        )
    cited = extract_citations(answer)
    allowed = {e.citation_id for e in evidence}
    unknown = [c for c in cited if c not in allowed]
    if unknown:
        return ValidatedAnswer(
            answer=answer,
            cited=cited,
            rejected_reason=f"answer cites unknown ids: {unknown[:3]}",
        )
    if limits.require_citations and not cited and evidence:
        return ValidatedAnswer(
            answer=answer,
            rejected_reason="answer has no citations but evidence was provided",
        )
    return ValidatedAnswer(answer=answer, cited=cited)


def validate_question(question: str, limits: GuardrailLimits) -> str:
    """Clip and reject overlong questions before any retrieval happens."""
    if not question or not question.strip():
        raise ValueError("question is empty")
    if len(question) > limits.max_question_chars:
        raise ValueError(
            f"question exceeds {limits.max_question_chars} characters"
        )
    return question.strip()
