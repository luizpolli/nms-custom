"""Tests for System / NetworkDevices / AlarmsEvents settings endpoints."""

from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.audit import AuditLog
from app.models.system import SystemSetting


# ---------------------------------------------------------------------------
# In-memory fake session that persists rows within a test via a dict store
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, value=None):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return []

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return 0


class FakeSession:
    """Minimal async session backed by an in-process dict."""

    def __init__(self, store: dict):
        self._store = store
        self._pending: list = []

    async def get(self, model_cls, key):
        return self._store.get(key)

    async def execute(self, *args, **kwargs):
        return _FakeResult()

    def add(self, obj):
        if isinstance(obj, SystemSetting):
            self._store[obj.key] = obj
        elif isinstance(obj, AuditLog):
            self._store.setdefault("__audit__", []).append(obj)

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def delete(self, obj):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(store: dict) -> TestClient:
    async def _fake_db() -> AsyncGenerator[FakeSession, None]:
        yield FakeSession(store)

    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# General settings tests
# ---------------------------------------------------------------------------

class TestGeneralSettings:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_get_returns_defaults(self):
        resp = self.client.get("/api/settings/general")
        assert resp.status_code == 200
        body = resp.json()
        assert body["product_name"] == "NMS Custom"
        assert body["default_theme"] == "system"

    def test_put_persists_and_audits(self):
        payload = {
            "product_name": "NMS Custom Lab",
            "deployment_name": "Certification",
            "default_theme": "dark",
            "support_contact_name": "NOC",
            "support_contact_email": "noc@example.com",
            "tac_case_url": "https://cisco.com/tac",
            "cisco_account_name": "lab-account",
        }
        resp = self.client.put("/api/settings/general", json=payload)
        assert resp.status_code == 200
        assert resp.json()["deployment_name"] == "Certification"
        assert self.store["__audit__"][-1].action == "settings.general.update"
        assert self.store["__audit__"][-1].object_id == "general"

    def test_put_invalid_support_email_rejected(self):
        payload = {
            "product_name": "NMS Custom",
            "deployment_name": "",
            "default_theme": "system",
            "support_contact_name": "",
            "support_contact_email": "bad-email",
            "tac_case_url": "",
            "cisco_account_name": "",
        }
        resp = self.client.put("/api/settings/general", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# System settings tests
# ---------------------------------------------------------------------------

class TestSystemSettings:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_get_returns_defaults(self):
        resp = self.client.get("/api/settings/system")
        assert resp.status_code == 200
        body = resp.json()
        assert "mail" in body
        assert "jobs" in body
        assert "retention" in body
        assert body["mail"]["smtp_port"] == 587
        assert body["jobs"]["job_concurrency"] == 4
        assert body["retention"]["alarm_retention_days"] == 90

    def test_viewer_api_key_cannot_read_system_settings(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "api_keys", "viewer-key")
        monkeypatch.setattr(settings, "api_key_roles", "viewer-key:viewer")

        resp = self.client.get("/api/settings/system", headers={"X-API-Key": "viewer-key"})
        assert resp.status_code == 403

    def test_admin_api_key_can_read_system_settings(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "api_auth_enabled", True)
        monkeypatch.setattr(settings, "api_keys", "admin-key")
        monkeypatch.setattr(settings, "api_key_roles", "admin-key:admin")

        resp = self.client.get("/api/settings/system", headers={"X-API-Key": "admin-key"})
        assert resp.status_code == 200
        assert resp.json()["jobs"]["job_concurrency"] == 4

    def test_put_persists_and_reflects(self):
        payload = {
            "mail": {"smtp_host": "mail.example.com", "smtp_port": 465,
                     "smtp_from": "nms@example.com", "smtp_use_tls": True, "smtp_username": "nms"},
            "jobs": {"job_concurrency": 8, "job_retry_backoff_seconds": 60, "job_max_retries": 5},
            "retention": {"alarm_retention_days": 180, "event_retention_days": 60,
                          "kpi_retention_days": 730, "telemetry_sample_retention_days": 14},
        }
        resp = self.client.put("/api/settings/system", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["mail"]["smtp_host"] == "mail.example.com"
        assert body["jobs"]["job_concurrency"] == 8
        assert body["retention"]["alarm_retention_days"] == 180
        assert self.store["__audit__"][-1].action == "settings.system.update"
        assert self.store["__audit__"][-1].object_id == "system"

    def test_put_invalid_email_rejected(self):
        payload = {
            "mail": {"smtp_from": "not-an-email", "smtp_port": 587,
                     "smtp_host": "", "smtp_use_tls": True, "smtp_username": ""},
            "jobs": {"job_concurrency": 4, "job_retry_backoff_seconds": 30, "job_max_retries": 3},
            "retention": {"alarm_retention_days": 90, "event_retention_days": 30,
                          "kpi_retention_days": 365, "telemetry_sample_retention_days": 7},
        }
        resp = self.client.put("/api/settings/system", json=payload)
        assert resp.status_code == 422

    def test_put_out_of_range_concurrency_rejected(self):
        payload = {
            "mail": {"smtp_from": "", "smtp_port": 587, "smtp_host": "",
                     "smtp_use_tls": True, "smtp_username": ""},
            "jobs": {"job_concurrency": 0, "job_retry_backoff_seconds": 30, "job_max_retries": 3},
            "retention": {"alarm_retention_days": 90, "event_retention_days": 30,
                          "kpi_retention_days": 365, "telemetry_sample_retention_days": 7},
        }
        resp = self.client.put("/api/settings/system", json=payload)
        assert resp.status_code == 422

    def test_get_after_put_reflects_saved_value(self):
        payload = {
            "mail": {"smtp_host": "relay.corp", "smtp_port": 25,
                     "smtp_from": "noc@corp.com", "smtp_use_tls": False, "smtp_username": ""},
            "jobs": {"job_concurrency": 2, "job_retry_backoff_seconds": 10, "job_max_retries": 1},
            "retention": {"alarm_retention_days": 45, "event_retention_days": 15,
                          "kpi_retention_days": 90, "telemetry_sample_retention_days": 3},
        }
        self.client.put("/api/settings/system", json=payload)
        resp = self.client.get("/api/settings/system")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mail"]["smtp_host"] == "relay.corp"
        assert body["retention"]["alarm_retention_days"] == 45

    def test_test_configuration_validates_current_payload(self):
        payload = self.client.get("/api/settings/system").json()["mail"]
        payload["smtp_host"] = "smtp.example.com"
        payload["smtp_from"] = ""

        resp = self.client.post("/api/settings/mail/test", json=payload)

        assert resp.status_code == 200
        assert resp.json()["ok"] is False
        assert "From address" in resp.json()["message"]

    def test_legacy_system_test_still_validates_mail_payload(self):
        payload = self.client.get("/api/settings/system").json()
        payload["mail"]["smtp_host"] = "smtp.example.com"
        payload["mail"]["smtp_from"] = ""

        resp = self.client.post("/api/settings/system/test", json=payload)

        assert resp.status_code == 200
        assert resp.json()["ok"] is False


# ---------------------------------------------------------------------------
# Network device settings tests
# ---------------------------------------------------------------------------

class TestNetworkDeviceSettings:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_get_returns_defaults(self):
        resp = self.client.get("/api/settings/network-devices")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cli"]["ssh_timeout_seconds"] == 30
        assert body["snmp"]["snmp_version"] == "v2c"
        assert body["snmp"]["polling_interval_seconds"] == 60

    def test_put_persists(self):
        payload = {
            "cli": {"ssh_timeout_seconds": 60, "ssh_port": 22, "cli_retries": 3,
                    "max_concurrent_ssh_sessions": 20, "terminal_length": 0},
            "snmp": {"snmp_version": "v3", "snmp_community": "secret",
                     "snmp_port": 161, "snmp_timeout_seconds": 10,
                     "snmp_retries": 3, "polling_interval_seconds": 300},
        }
        resp = self.client.put("/api/settings/network-devices", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["cli"]["ssh_timeout_seconds"] == 60
        assert body["snmp"]["snmp_version"] == "v3"
        assert self.store["__audit__"][-1].action == "settings.network_devices.update"
        assert self.store["__audit__"][-1].object_id == "network_devices"

    def test_put_invalid_timeout_rejected(self):
        payload = {
            "cli": {"ssh_timeout_seconds": 0, "ssh_port": 22, "cli_retries": 2,
                    "max_concurrent_ssh_sessions": 10, "terminal_length": 0},
            "snmp": {"snmp_version": "v2c", "snmp_community": "public",
                     "snmp_port": 161, "snmp_timeout_seconds": 5,
                     "snmp_retries": 2, "polling_interval_seconds": 60},
        }
        resp = self.client.put("/api/settings/network-devices", json=payload)
        assert resp.status_code == 422

    def test_get_after_put_reflects(self):
        payload = {
            "cli": {"ssh_timeout_seconds": 45, "ssh_port": 830, "cli_retries": 1,
                    "max_concurrent_ssh_sessions": 5, "terminal_length": 0},
            "snmp": {"snmp_version": "v2c", "snmp_community": "mgmt",
                     "snmp_port": 161, "snmp_timeout_seconds": 3,
                     "snmp_retries": 1, "polling_interval_seconds": 120},
        }
        self.client.put("/api/settings/network-devices", json=payload)
        resp = self.client.get("/api/settings/network-devices")
        assert resp.status_code == 200
        assert resp.json()["cli"]["ssh_timeout_seconds"] == 45


# ---------------------------------------------------------------------------
# Alarms/Events settings tests
# ---------------------------------------------------------------------------

class TestAlarmsEventsSettings:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_get_returns_defaults(self):
        resp = self.client.get("/api/settings/alarms-events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["notifications"]["min_severity_to_notify"] == "major"
        assert body["suppression"]["suppression_window_minutes"] == 5

    def test_put_persists(self):
        payload = {
            "severity_mapping": {"critical_oid_value": 1, "major_oid_value": 2,
                                  "minor_oid_value": 3, "warning_oid_value": 4, "info_oid_value": 5},
            "notifications": {"email_enabled": True,
                               "email_recipients": "noc@corp.com,admin@corp.com",
                               "syslog_forward_enabled": True,
                               "syslog_forward_host": "syslog.corp.com",
                               "syslog_forward_port": 514,
                               "min_severity_to_notify": "critical"},
            "suppression": {"suppression_window_minutes": 10,
                            "flap_detection_enabled": True, "flap_threshold_count": 5},
        }
        resp = self.client.put("/api/settings/alarms-events", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["notifications"]["email_enabled"] is True
        assert body["notifications"]["min_severity_to_notify"] == "critical"
        assert self.store["__audit__"][-1].action == "settings.alarms_events.update"
        assert self.store["__audit__"][-1].object_id == "alarms_events"

    def test_put_invalid_syslog_host_rejected(self):
        payload = {
            "severity_mapping": {"critical_oid_value": 1, "major_oid_value": 2,
                                  "minor_oid_value": 3, "warning_oid_value": 4, "info_oid_value": 5},
            "notifications": {"email_enabled": False,
                               "email_recipients": "",
                               "syslog_forward_enabled": True,
                               "syslog_forward_host": "bad host\ninjection",
                               "syslog_forward_port": 514,
                               "min_severity_to_notify": "major"},
            "suppression": {"suppression_window_minutes": 5,
                            "flap_detection_enabled": True, "flap_threshold_count": 3},
        }
        resp = self.client.put("/api/settings/alarms-events", json=payload)
        assert resp.status_code == 422

    def test_get_after_put_reflects(self):
        payload = {
            "severity_mapping": {"critical_oid_value": 1, "major_oid_value": 2,
                                  "minor_oid_value": 3, "warning_oid_value": 4, "info_oid_value": 5},
            "notifications": {"email_enabled": False, "email_recipients": "",
                               "syslog_forward_enabled": False, "syslog_forward_host": "",
                               "syslog_forward_port": 514, "min_severity_to_notify": "warning"},
            "suppression": {"suppression_window_minutes": 15,
                            "flap_detection_enabled": False, "flap_threshold_count": 3},
        }
        self.client.put("/api/settings/alarms-events", json=payload)
        resp = self.client.get("/api/settings/alarms-events")
        assert resp.status_code == 200
        assert resp.json()["suppression"]["suppression_window_minutes"] == 15


# ---------------------------------------------------------------------------
# Inventory / integrations / lab settings tests
# ---------------------------------------------------------------------------

class TestAdditionalSettingsSections:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_inventory_put_persists(self):
        payload = {
            "config_archive_enabled": True,
            "config_archive_frequency_minutes": 720,
            "config_archive_retention_days": 120,
            "image_repository_path": "/var/lib/nms/images",
            "default_discovery_profile": "snmp-v3",
            "auto_group_by_site": False,
            "lifecycle_warning_days": 90,
        }
        resp = self.client.put("/api/settings/inventory", json=payload)
        assert resp.status_code == 200
        assert resp.json()["default_discovery_profile"] == "snmp-v3"
        assert self.client.get("/api/settings/inventory").json()["config_archive_retention_days"] == 120
        assert self.store["__audit__"][-1].action == "settings.inventory.update"

    def test_inventory_invalid_archive_frequency_rejected(self):
        payload = self.client.get("/api/settings/inventory").json()
        payload["config_archive_frequency_minutes"] = 1
        resp = self.client.put("/api/settings/inventory", json=payload)
        assert resp.status_code == 422

    def test_bulkstats_get_returns_defaults(self):
        resp = self.client.get("/api/settings/bulkstats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["raw_sample_retention_days"] == 30
        assert body["watch"]["enabled"] is True
        assert body["pull"]["enabled"] is True

    def test_bulkstats_put_persists_custom_retention_and_paths(self):
        payload = {
            "raw_sample_retention_days": 14,
            "watch": {"enabled": True, "watch_path": "/srv/bulkstats/drop", "poll_interval_seconds": 30},
            "pull": {"enabled": False, "remote_path": "/flash/custom-bulkstats", "poll_interval_seconds": 1800},
        }
        resp = self.client.put("/api/settings/bulkstats", json=payload)
        assert resp.status_code == 200
        assert resp.json()["raw_sample_retention_days"] == 14
        fetched = self.client.get("/api/settings/bulkstats").json()
        assert fetched["watch"]["watch_path"] == "/srv/bulkstats/drop"
        assert fetched["pull"]["remote_path"] == "/flash/custom-bulkstats"
        assert fetched["pull"]["enabled"] is False
        assert self.store["__audit__"][-1].action == "settings.bulkstats.update"

    def test_bulkstats_invalid_retention_days_rejected(self):
        payload = self.client.get("/api/settings/bulkstats").json()
        payload["raw_sample_retention_days"] = 0
        resp = self.client.put("/api/settings/bulkstats", json=payload)
        assert resp.status_code == 422

    def test_integrations_ai_ops_put_persists(self):
        payload = {"ai_ops_enabled": False}
        resp = self.client.put("/api/settings/integrations-ai-ops", json=payload)
        assert resp.status_code == 200
        assert resp.json()["ai_ops_enabled"] is False
        assert self.store["__audit__"][-1].action == "settings.integrations_ai_ops.update"

    def test_integrations_ai_ops_get_includes_effective_runtime_config(self):
        resp = self.client.get("/api/settings/integrations-ai-ops")
        assert resp.status_code == 200
        body = resp.json()
        assert "effective_llm_enabled" in body
        assert "effective_llm_provider" in body
        assert "effective_llm_model" in body
        assert "effective_llm_base_url" in body

    def test_integrations_ai_ops_put_rejects_invalid_type(self):
        resp = self.client.put(
            "/api/settings/integrations-ai-ops", json={"ai_ops_enabled": "not-a-bool"}
        )
        assert resp.status_code == 422

    def test_lab_operations_put_persists(self):
        payload = {
            "certification_mode_enabled": True,
            "traffic_simulator_enabled": True,
            "simulator_profile": "trap-storm",
            "maintenance_mode_enabled": False,
            "maintenance_window": "Sunday 01:00-03:00",
            "runbook_url": "https://example.com/runbook",
            "ptp_synce_enabled": True,
        }
        resp = self.client.put("/api/settings/lab-operations", json=payload)
        assert resp.status_code == 200
        assert resp.json()["simulator_profile"] == "trap-storm"
        assert self.client.get("/api/settings/lab-operations").json()["ptp_synce_enabled"] is True
        assert self.store["__audit__"][-1].action == "settings.lab_operations.update"

    def test_lab_operations_invalid_runbook_rejected(self):
        payload = self.client.get("/api/settings/lab-operations").json()
        payload["runbook_url"] = "ftp://example.com/runbook"
        resp = self.client.put("/api/settings/lab-operations", json=payload)
        assert resp.status_code == 422

    def test_modules_put_persists_and_audits(self):
        payload = self.client.get("/api/settings/modules").json()
        payload["telemetry"] = False
        payload["commands"] = False

        resp = self.client.put("/api/settings/modules", json=payload)

        assert resp.status_code == 200
        assert self.client.get("/api/settings/modules").json()["telemetry"] is False
        assert self.client.get("/api/settings/modules").json()["commands"] is False
        assert self.store["__audit__"][-1].action == "settings.modules.update"
        assert sorted(self.store["__audit__"][-1].details["disabled"]) == ["commands", "telemetry"]

    def test_account_audit_paths_returns_cli_targets(self):
        resp = self.client.get("/api/settings/account-audit/paths")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_activity_path"].endswith("account_audit.jsonl")
        assert body["privileged_activity_path"].endswith("privileged_account_audit.jsonl")


# ---------------------------------------------------------------------------
# Settings profile import/export tests
# ---------------------------------------------------------------------------

class TestSettingsProfile:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_export_profile_returns_all_backend_backed_sections(self):
        resp = self.client.get("/api/settings/profile")
        assert resp.status_code == 200
        body = resp.json()

        assert body["profile_version"] == 3
        assert body["general"]["product_name"] == "NMS Custom"
        assert body["security"]["tls_min_version"] in {"TLSv1.2", "TLSv1.3"}
        assert body["system"]["mail"]["smtp_port"] == 587
        assert body["network_devices"]["snmp"]["snmp_port"] == 161
        assert body["inventory"]["config_archive_retention_days"] == 90
        assert body["alarms_events"]["notifications"]["min_severity_to_notify"] == "major"
        assert body["integrations_ai_ops"]["ai_ops_enabled"] is True
        assert body["lab_operations"]["certification_mode_enabled"] is True
        assert body["modules"]["telemetry"] is True
        assert self.store["__audit__"][-1].action == "settings.profile.export"

    def test_import_profile_persists_all_sections(self):
        payload = self.client.get("/api/settings/profile").json()
        payload["security"]["api_auth_enabled"] = True
        payload["general"]["deployment_name"] = "Profile import"
        payload["system"]["mail"]["smtp_host"] = "smtp.profile.local"
        payload["network_devices"]["cli"]["ssh_timeout_seconds"] = 75
        payload["inventory"]["default_discovery_profile"] = "profile-discovery"
        payload["alarms_events"]["suppression"]["suppression_window_minutes"] = 22
        payload["integrations_ai_ops"]["ai_ops_enabled"] = False
        payload["lab_operations"]["simulator_profile"] = "profile-sim"
        payload["modules"]["telemetry"] = False

        resp = self.client.put("/api/settings/profile", json=payload)
        assert resp.status_code == 200

        assert self.client.get("/api/settings/security").json()["api_auth_enabled"] is True
        assert self.client.get("/api/settings/general").json()["deployment_name"] == "Profile import"
        assert self.client.get("/api/settings/system").json()["mail"]["smtp_host"] == "smtp.profile.local"
        assert self.client.get("/api/settings/network-devices").json()["cli"]["ssh_timeout_seconds"] == 75
        assert self.client.get("/api/settings/inventory").json()["default_discovery_profile"] == "profile-discovery"
        assert self.client.get("/api/settings/alarms-events").json()["suppression"]["suppression_window_minutes"] == 22
        assert self.client.get("/api/settings/integrations-ai-ops").json()["ai_ops_enabled"] is False
        assert self.client.get("/api/settings/lab-operations").json()["simulator_profile"] == "profile-sim"
        assert self.client.get("/api/settings/modules").json()["telemetry"] is False
        assert any(entry.action == "settings.profile.import" for entry in self.store["__audit__"])

    def test_import_profile_rejects_unknown_version(self):
        payload = self.client.get("/api/settings/profile").json()
        payload["profile_version"] = 999

        resp = self.client.put("/api/settings/profile", json=payload)
        assert resp.status_code == 400
        assert "Unsupported settings profile version" in resp.json()["detail"]

    def test_import_profile_rejects_incomplete_https_config(self):
        payload = self.client.get("/api/settings/profile").json()
        payload["security"]["https_enabled"] = True
        payload["security"]["tls_cert_file"] = ""
        payload["security"]["tls_key_file"] = ""

        resp = self.client.put("/api/settings/profile", json=payload)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "HTTPS requires certificate and key file paths"
