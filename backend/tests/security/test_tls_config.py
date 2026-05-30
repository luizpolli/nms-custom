"""Security regression tests: TLS/HTTPS configuration.

Tests the ``_ssl_context`` factory in ``app.server`` and the settings-level
TLS validation in ``app.config`` (production safety guard).  Together they
ensure the server cannot accidentally start with:

  - TLS 1.0 / 1.1 (weak protocols)
  - Missing cert/key files
  - HTTPS disabled in production
  - A minimum version that is not TLSv1.2 or TLSv1.3
"""

from __future__ import annotations

import secrets
import ssl
import tempfile
from pathlib import Path

import pytest

from app.config import ProductionSafetyError, Settings
from app.server import _ssl_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_prod_env(**overrides: str) -> dict[str, str]:
    """Return a minimal set of safe production settings, with optional overrides."""
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


# ---------------------------------------------------------------------------
# _ssl_context: disabled
# ---------------------------------------------------------------------------


def test_ssl_context_returns_none_when_https_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No SSL context must be created when HTTPS is off."""
    from app import server
    from app.config import settings

    monkeypatch.setattr(settings, "https_enabled", False)
    ctx = _ssl_context()
    assert ctx is None


# ---------------------------------------------------------------------------
# _ssl_context: missing cert files
# ---------------------------------------------------------------------------


def test_ssl_context_raises_when_cert_file_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup must abort when cert/key paths are empty strings."""
    from app.config import settings

    monkeypatch.setattr(settings, "https_enabled", True)
    monkeypatch.setattr(settings, "tls_cert_file", "")
    monkeypatch.setattr(settings, "tls_key_file", "")
    with pytest.raises(RuntimeError, match="TLS_CERT_FILE"):
        _ssl_context()


def test_ssl_context_raises_when_cert_path_is_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup must abort when only the cert path is empty."""
    from app.config import settings

    monkeypatch.setattr(settings, "https_enabled", True)
    monkeypatch.setattr(settings, "tls_cert_file", "")
    monkeypatch.setattr(settings, "tls_key_file", "/certs/server.key")
    with pytest.raises(RuntimeError):
        _ssl_context()


# ---------------------------------------------------------------------------
# _ssl_context: minimum version mapping
# ---------------------------------------------------------------------------


def test_ssl_context_tls13_sets_minimum_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """TLS_MIN_VERSION=TLSv1.3 must set ctx.minimum_version to TLSv1_3."""
    from app.config import settings
    from app.server import _ensure_development_cert

    cert = tmp_path / "server.crt"
    key = tmp_path / "server.key"
    _ensure_development_cert(cert, key)

    monkeypatch.setattr(settings, "https_enabled", True)
    monkeypatch.setattr(settings, "tls_min_version", "TLSv1.3")
    monkeypatch.setattr(settings, "tls_cert_file", str(cert))
    monkeypatch.setattr(settings, "tls_key_file", str(key))
    monkeypatch.setattr(settings, "tls_ca_file", "")

    ctx = _ssl_context()
    assert ctx is not None
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3


def test_ssl_context_tls12_sets_minimum_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """TLS_MIN_VERSION=TLSv1.2 must set ctx.minimum_version to TLSv1_2."""
    from app.config import settings
    from app.server import _ensure_development_cert

    cert = tmp_path / "server.crt"
    key = tmp_path / "server.key"
    _ensure_development_cert(cert, key)

    monkeypatch.setattr(settings, "https_enabled", True)
    monkeypatch.setattr(settings, "tls_min_version", "TLSv1.2")
    monkeypatch.setattr(settings, "tls_cert_file", str(cert))
    monkeypatch.setattr(settings, "tls_key_file", str(key))
    monkeypatch.setattr(settings, "tls_ca_file", "")

    ctx = _ssl_context()
    assert ctx is not None
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


# ---------------------------------------------------------------------------
# Settings-level TLS validation (production safety guard)
# ---------------------------------------------------------------------------


def test_production_rejects_tls10(monkeypatch: pytest.MonkeyPatch) -> None:
    """TLS_MIN_VERSION=TLSv1.0 must be refused in production."""
    _apply_env(monkeypatch, _safe_prod_env(TLS_MIN_VERSION="TLSv1.0"))
    with pytest.raises(ProductionSafetyError) as exc:
        Settings(_env_file=None)
    assert any("TLS_MIN_VERSION" in i for i in exc.value.issues)


def test_production_rejects_tls11(monkeypatch: pytest.MonkeyPatch) -> None:
    """TLS_MIN_VERSION=TLSv1.1 must be refused in production."""
    _apply_env(monkeypatch, _safe_prod_env(TLS_MIN_VERSION="TLSv1.1"))
    with pytest.raises(ProductionSafetyError) as exc:
        Settings(_env_file=None)
    assert any("TLS_MIN_VERSION" in i for i in exc.value.issues)


def test_production_rejects_garbage_tls_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """A completely invalid TLS_MIN_VERSION value must be refused in production."""
    _apply_env(monkeypatch, _safe_prod_env(TLS_MIN_VERSION="SSL3.0"))
    with pytest.raises(ProductionSafetyError) as exc:
        Settings(_env_file=None)
    assert any("TLS_MIN_VERSION" in i for i in exc.value.issues)


def test_production_accepts_tls12(monkeypatch: pytest.MonkeyPatch) -> None:
    """TLS_MIN_VERSION=TLSv1.2 is the minimum accepted in production."""
    _apply_env(monkeypatch, _safe_prod_env(TLS_MIN_VERSION="TLSv1.2"))
    s = Settings(_env_file=None)
    assert s.tls_min_version == "TLSv1.2"


def test_production_accepts_tls13(monkeypatch: pytest.MonkeyPatch) -> None:
    """TLS_MIN_VERSION=TLSv1.3 is the recommended default for production."""
    _apply_env(monkeypatch, _safe_prod_env(TLS_MIN_VERSION="TLSv1.3"))
    s = Settings(_env_file=None)
    assert s.tls_min_version == "TLSv1.3"


def test_production_rejects_https_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPS_ENABLED=false must be refused in production."""
    _apply_env(monkeypatch, _safe_prod_env(HTTPS_ENABLED="false"))
    with pytest.raises(ProductionSafetyError) as exc:
        Settings(_env_file=None)
    assert any("HTTPS_ENABLED" in i for i in exc.value.issues)


def test_development_allows_https_disabled() -> None:
    """HTTP-only is valid for local development (default)."""
    s = Settings(app_env="development", https_enabled=False, _env_file=None)
    assert s.https_enabled is False
