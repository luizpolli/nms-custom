"""Tests for the AI Ops assistant guardrails and orchestrator."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass

import pytest
import httpx

from app.services.ai_ops.assistant import answer_question
from app.services.ai_ops.guardrails import (
    EvidenceItem,
    GuardrailLimits,
    extract_citations,
    redact_text,
    validate_answer,
    validate_question,
)
from app.services.ai_ops.providers import (
    LLMRequest,
    NullLLMProvider,
    OpenAICompatibleProvider,
    get_provider,
)


# --- redaction ---------------------------------------------------------------


def test_redact_ipv4_and_mac_and_fqdn():
    text = "host nms.example.com 10.1.2.3 mac aa:bb:cc:dd:ee:ff"
    out = redact_text(text)
    assert "10.1.2.3" not in out
    assert "aa:bb:cc:dd:ee:ff" not in out
    assert "nms.example.com" not in out
    assert "[REDACTED_IP]" in out
    assert "[REDACTED_MAC]" in out


def test_redact_password_and_snmp_community():
    text = "password=hunter2 community public123"
    out = redact_text(text)
    assert "hunter2" not in out
    assert "public123" not in out


def test_redact_private_key_block():
    block = "-----BEGIN RSA PRIVATE KEY-----\nabcd\n-----END RSA PRIVATE KEY-----"
    out = redact_text(block)
    assert "abcd" not in out
    assert "[REDACTED_PRIVATE_KEY]" in out


# --- citation validation -----------------------------------------------------


def _evidence(*ids: str) -> list[EvidenceItem]:
    return [EvidenceItem(citation_id=i, source_type="alarm", label="x") for i in ids]


def test_extract_citations_pulls_tagged_ids():
    assert extract_citations("foo [alarm:1] bar [kpi:2]") == ["alarm:1", "kpi:2"]


def test_validate_answer_rejects_unknown_citation():
    res = validate_answer("foo [alarm:99]", _evidence("alarm:1"), GuardrailLimits())
    assert not res.ok
    assert "unknown" in (res.rejected_reason or "")


def test_validate_answer_rejects_missing_citation_when_evidence_exists():
    res = validate_answer("hola sin citas", _evidence("alarm:1"), GuardrailLimits())
    assert not res.ok


def test_validate_answer_accepts_known_citation():
    res = validate_answer("ok [alarm:1]", _evidence("alarm:1"), GuardrailLimits())
    assert res.ok
    assert res.cited == ["alarm:1"]


def test_validate_answer_rejects_empty():
    assert not validate_answer("", _evidence(), GuardrailLimits()).ok


def test_validate_question_rejects_blank_and_overlong():
    limits = GuardrailLimits(max_question_chars=20)
    with pytest.raises(ValueError):
        validate_question("   ", limits)
    with pytest.raises(ValueError):
        validate_question("x" * 21, limits)


# --- providers ---------------------------------------------------------------


def test_get_provider_returns_null_by_default():
    p = get_provider(None)
    assert p.name == "null"


def test_get_provider_rejects_unknown():
    with pytest.raises(ValueError):
        get_provider("totally-not-a-real-provider")


def test_get_provider_openai_requires_api_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_ops_llm_api_key", "")
    monkeypatch.setattr(settings, "ai_ops_llm_model", "test-model")
    with pytest.raises(ValueError):
        get_provider("openai-compatible")


def test_null_provider_emits_citations_for_each_evidence_item():
    provider = NullLLMProvider()
    ev = _evidence("alarm:1", "kpi:2")
    out = asyncio.run(
        provider.complete(LLMRequest(system="s", user="u", evidence=ev))
    )
    assert "[alarm:1]" in out
    assert "[kpi:2]" in out


def test_null_provider_handles_empty_evidence():
    out = asyncio.run(
        NullLLMProvider().complete(LLMRequest(system="s", user="u", evidence=[]))
    )
    assert "evidencia" in out.lower()


def test_openai_compatible_provider_sends_redacted_prompt_and_parses_answer():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Revisa la alarma citada [alarm:1]."}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    async def _run() -> str:
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                api_key="secret-key",
                model="test-model",
                base_url="https://llm.local/v1",
                client=client,
            )
            return await provider.complete(
                LLMRequest(
                    system="system",
                    user="user prompt [alarm:1]",
                    evidence=_evidence("alarm:1"),
                )
            )

    out = asyncio.run(_run())
    assert out == "Revisa la alarma citada [alarm:1]."
    assert seen["authorization"] == "Bearer secret-key"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "test-model"
    assert payload["messages"][1]["content"] == "user prompt [alarm:1]"


def test_openai_compatible_provider_rejects_invalid_payload():
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"choices": []}))

    async def _run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                api_key="secret-key",
                model="test-model",
                client=client,
            )
            await provider.complete(LLMRequest(system="system", user="user", evidence=[]))

    with pytest.raises(ValueError):
        asyncio.run(_run())


# --- orchestrator with fake DB ----------------------------------------------


@dataclass
class _FakeKpi:
    id: uuid.UUID
    metric_name: str
    kpi_type: str
    value: float
    quality: str


@dataclass
class _FakeAlarm:
    id: uuid.UUID
    message: str
    severity: str
    state: str
    category: str


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, alarms, kpis):
        self._alarms = alarms
        self._kpis = kpis
        self._calls = 0

    async def execute(self, _stmt):
        self._calls += 1
        return _FakeResult(self._alarms if self._calls == 1 else self._kpis)


def test_answer_question_returns_citations_with_null_provider():
    alarm = _FakeAlarm(
        id=uuid.uuid4(),
        message="Link down on 10.0.0.1",
        severity="major",
        state="active",
        category="link",
    )
    kpi = _FakeKpi(
        id=uuid.uuid4(),
        metric_name="cpu",
        kpi_type="cpu",
        value=95.0,
        quality="warning",
    )
    db = _FakeSession([alarm], [kpi])

    result = asyncio.run(answer_question(db, "¿qué pasa con el enlace?"))

    assert result.rejected_reason is None
    assert result.provider == "null"
    assert any(c.citation_id == f"alarm:{alarm.id}" for c in result.citations)
    assert any(c.citation_id == f"kpi:{kpi.id}" for c in result.citations)
    # IP must have been redacted before being shown in the citation label.
    alarm_label = next(c.label for c in result.citations if c.source_type == "alarm")
    assert "10.0.0.1" not in alarm_label


def test_answer_question_rejects_blank():
    db = _FakeSession([], [])
    with pytest.raises(ValueError):
        asyncio.run(answer_question(db, "   "))
