"""Route-level tests for POST /ai-ops/assistant/ask enablement gating.

The endpoint must be disabled unless BOTH the infra-level env flag
(AI_OPS_LLM_ENABLED) and the admin-level DB toggle (Settings > Integrations /
AI Ops > "Enable AI Ops recommendations") are on.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app
from tests.api.test_settings_admin import FakeSession


def _make_client(store: dict) -> TestClient:
    async def _fake_db() -> AsyncGenerator[FakeSession, None]:
        yield FakeSession(store)

    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app, raise_server_exceptions=True)


class TestAssistantAskEnablement:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_disabled_when_env_flag_off(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "ai_ops_llm_enabled", False)
        resp = self.client.post("/api/ai-ops/assistant/ask", json={"question": "status?"})
        assert resp.status_code == 503

    def test_disabled_when_admin_toggle_off(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "ai_ops_llm_enabled", True)
        self.client.put("/api/settings/integrations-ai-ops", json={"ai_ops_enabled": False})
        resp = self.client.post("/api/ai-ops/assistant/ask", json={"question": "status?"})
        assert resp.status_code == 503

    def test_enabled_when_both_flags_on(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(settings, "ai_ops_llm_enabled", True)
        monkeypatch.setattr(settings, "ai_ops_llm_provider", "null")
        self.client.put("/api/settings/integrations-ai-ops", json={"ai_ops_enabled": True})
        resp = self.client.post("/api/ai-ops/assistant/ask", json={"question": "status?"})
        assert resp.status_code == 200
        assert resp.json()["provider"] == "null"
