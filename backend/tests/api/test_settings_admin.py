"""Tests for System / NetworkDevices / AlarmsEvents settings endpoints."""

from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
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

        assert body["profile_version"] == 1
        assert body["security"]["tls_min_version"] in {"TLSv1.2", "TLSv1.3"}
        assert body["system"]["mail"]["smtp_port"] == 587
        assert body["network_devices"]["snmp"]["snmp_port"] == 161
        assert body["alarms_events"]["notifications"]["min_severity_to_notify"] == "major"

    def test_import_profile_persists_all_sections(self):
        payload = self.client.get("/api/settings/profile").json()
        payload["security"]["api_auth_enabled"] = True
        payload["system"]["mail"]["smtp_host"] = "smtp.profile.local"
        payload["network_devices"]["cli"]["ssh_timeout_seconds"] = 75
        payload["alarms_events"]["suppression"]["suppression_window_minutes"] = 22

        resp = self.client.put("/api/settings/profile", json=payload)
        assert resp.status_code == 200

        assert self.client.get("/api/settings/security").json()["api_auth_enabled"] is True
        assert self.client.get("/api/settings/system").json()["mail"]["smtp_host"] == "smtp.profile.local"
        assert self.client.get("/api/settings/network-devices").json()["cli"]["ssh_timeout_seconds"] == 75
        assert self.client.get("/api/settings/alarms-events").json()["suppression"]["suppression_window_minutes"] == 22

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
