"""Provider-agnostic LLM client interface for AI Ops.

The default `NullLLMProvider` is deterministic and does not call any external
service. Real provider adapters (Anthropic, OpenAI, vLLM, Bedrock, ...) must
implement `LLMProvider.complete` and respect the redacted prompt contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

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


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible chat completions adapter.

    Works with OpenAI's `/v1/chat/completions` shape and compatible local/hosted
    gateways. The assistant orchestrator already redacts prompts and validates
    citations after the provider returns.
    """

    name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ai_ops_llm_api_key is required for openai-compatible provider")
        if not model:
            raise ValueError("ai_ops_llm_model is required for openai-compatible provider")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def complete(self, request: LLMRequest) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        if self._client is not None:
            response = await self._client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)

        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM provider returned an invalid chat completion payload") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM provider returned an empty answer")
        return content.strip()


def get_provider(name: str | None) -> LLMProvider:
    """Return a provider by name."""
    key = (name or "null").strip().lower()
    if key in ("", "null", "none", "off", "disabled"):
        return NullLLMProvider()
    if key in ("openai", "openai-compatible", "chat-completions"):
        from app.config import settings

        return OpenAICompatibleProvider(
            api_key=settings.ai_ops_llm_api_key,
            model=settings.ai_ops_llm_model,
            base_url=settings.ai_ops_llm_base_url,
            timeout_seconds=settings.ai_ops_llm_timeout_seconds,
        )
    raise ValueError(
        f"unknown ai_ops provider '{name}'. Implement LLMProvider and register it."
    )
