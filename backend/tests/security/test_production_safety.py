"""Tests for the APP_ENV=production fail-fast guard in app.config.

The guard refuses to boot the app when sensitive defaults are still present,
and lists every issue at once so operators don't fix-restart-discover-fix in
a loop. See P0.3 in the prod-readiness audit.
"""

from __future__ import annotations

import secrets

import pytest

from app.config import ProductionSafetyError, Settings


# A complete set of safe overrides so individual tests only have to break one
# thing at a time. Values are high-entropy and avoid the placeholder fragments
# the guard scans for ("change-me", "change…").
def _safe_prod_env(**overrides: str) -> dict[str, str]:
    base = {
        "APP_ENV": "production",
        "DEBUG": "false",
        "SECRET_KEY": secrets.token_hex(32),
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "SNMP_DEFAULT_COMMUNITY": secrets.token_hex(16),
        "CREDENTIAL_ENCRYPTION_KEY": secrets.token_hex(32),
        "CREDENTIAL_ENCRYPTION_IV": secrets.token_hex(16),
        "API_AUTH_ENABLED": "true",
        "API_KEYS": f"{secrets.token_hex(24)},{secrets.token_hex(24)}",
        "HTTPS_ENABLED": "true",
        "HTTPS_REDIRECT_ENABLED": "true",
        "TLS_MIN_VERSION": "TLSv1.3",
        "TLS_CERT_FILE": "/certs/server.crt",
        "TLS_KEY_FILE": "/certs/server.key",
        "SSH_DISABLE_HOST_KEY_CHECKING": "false",
    }
    base.update(overrides)
    return base


def _apply_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_development_default_does_not_trigger_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default (development) config must always boot, even with unsafe defaults."""
    # Clear anything the test runner injected so we get vanilla defaults.
    for key in ("APP_ENV", "API_AUTH_ENABLED", "HTTPS_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    s = Settings(_env_file=None)
    assert s.app_env == "development"


def test_test_env_does_not_trigger_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_ENV=test (used by conftest) must skip the guard entirely."""
    monkeypatch.setenv("APP_ENV", "test")
    s = Settings(_env_file=None)
    assert s.app_env == "test"


def test_production_with_safe_values_boots(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fully-configured production env should boot without raising."""
    _apply_env(monkeypatch, _safe_prod_env())
    s = Settings(_env_file=None)
    assert s.app_env == "production"
    assert s.https_enabled is True
    assert s.api_auth_enabled is True


def test_production_with_default_secret_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(SECRET_KEY="change-me-to-a-real-secret-key")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("SECRET_KEY" in i for i in excinfo.value.issues)


def test_production_with_default_postgres_password_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(POSTGRES_PASSWORD="nms_secret")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("POSTGRES_PASSWORD" in i for i in excinfo.value.issues)


def test_production_with_public_snmp_community_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(SNMP_DEFAULT_COMMUNITY="public")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("SNMP_DEFAULT_COMMUNITY" in i for i in excinfo.value.issues)


def test_production_with_placeholder_fragment_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 'change-me' fragment is a placeholder regardless of suffix."""
    env = _safe_prod_env(SECRET_KEY="change-me-please-i-am-very-long-xxxxxxxxxxxxxx")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("SECRET_KEY" in i for i in excinfo.value.issues)


def test_production_with_short_secret_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anything below 16 chars is rejected as low-entropy."""
    env = _safe_prod_env(SECRET_KEY="shorty")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("SECRET_KEY" in i and "characters" in i for i in excinfo.value.issues)


def test_production_with_empty_credential_keys_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(CREDENTIAL_ENCRYPTION_KEY="", CREDENTIAL_ENCRYPTION_IV="")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    issues = excinfo.value.issues
    assert any("CREDENTIAL_ENCRYPTION_KEY" in i for i in issues)
    assert any("CREDENTIAL_ENCRYPTION_IV" in i for i in issues)


def test_production_with_api_auth_disabled_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(API_AUTH_ENABLED="false")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("API_AUTH_ENABLED" in i for i in excinfo.value.issues)


def test_production_with_empty_api_keys_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(API_KEYS="")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("API_KEYS" in i for i in excinfo.value.issues)


def test_production_with_placeholder_api_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(API_KEYS="change-me-admin-key,change-me-aiops-key")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("API_KEYS" in i for i in excinfo.value.issues)


def test_production_accepts_sha256_prefixed_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The auth layer supports `sha256$<hex-digest>` entries; guard must too."""
    digest = secrets.token_hex(32)  # 64 hex chars, well above min length
    env = _safe_prod_env(API_KEYS=f"sha256${digest}")
    _apply_env(monkeypatch, env)
    s = Settings(_env_file=None)
    assert s.api_auth_enabled is True


def test_production_with_debug_true_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(DEBUG="true")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("DEBUG" in i for i in excinfo.value.issues)


def test_production_with_https_disabled_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(HTTPS_ENABLED="false")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("HTTPS_ENABLED" in i for i in excinfo.value.issues)


def test_production_with_unsupported_tls_version_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _safe_prod_env(TLS_MIN_VERSION="TLSv1.0")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("TLS_MIN_VERSION" in i for i in excinfo.value.issues)


def test_production_with_ssh_host_key_checking_disabled_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _safe_prod_env(SSH_DISABLE_HOST_KEY_CHECKING="true")
    _apply_env(monkeypatch, env)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    assert any("SSH_DISABLE_HOST_KEY_CHECKING" in i for i in excinfo.value.issues)


def test_production_reports_all_issues_in_one_shot(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard must surface every blocker, not stop at the first one."""
    bad = _safe_prod_env(
        SECRET_KEY="change-me-to-a-real-secret-key",
        POSTGRES_PASSWORD="nms_secret",
        SNMP_DEFAULT_COMMUNITY="public",
        CREDENTIAL_ENCRYPTION_KEY="",
        CREDENTIAL_ENCRYPTION_IV="",
        API_AUTH_ENABLED="false",
        DEBUG="true",
        HTTPS_ENABLED="false",
    )
    _apply_env(monkeypatch, bad)
    with pytest.raises(ProductionSafetyError) as excinfo:
        Settings(_env_file=None)
    # Expect at least one issue per category we broke.
    issues = excinfo.value.issues
    assert len(issues) >= 7, issues
