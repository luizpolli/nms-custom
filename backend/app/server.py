"""Production server launcher with optional TLS 1.3 HTTPS."""

from __future__ import annotations

import ssl
import subprocess
from pathlib import Path

import uvicorn

from app.config import settings


def _ssl_context() -> ssl.SSLContext | None:
    if not settings.https_enabled:
        return None
    if not settings.tls_cert_file or not settings.tls_key_file:
        raise RuntimeError("HTTPS enabled but TLS_CERT_FILE/TLS_KEY_FILE are not configured")
    _ensure_development_cert(Path(settings.tls_cert_file), Path(settings.tls_key_file))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3 if settings.tls_min_version == "TLSv1.3" else ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(settings.tls_cert_file, settings.tls_key_file)
    if settings.tls_ca_file:
        ctx.load_verify_locations(settings.tls_ca_file)
    return ctx


def _ensure_development_cert(cert_file: Path, key_file: Path) -> None:
    """Create a local self-signed certificate only when no configured cert exists."""
    if cert_file.exists() and key_file.exists():
        return
    cert_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:4096", "-sha256", "-days", "365",
            "-nodes", "-keyout", str(key_file), "-out", str(cert_file),
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1,DNS:app,DNS:frontend",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    bind_host = "0.0.0.0"  # nosec B104 - container listener; ingress/firewall controls exposure.
    uvicorn.run(
        "app.main:app",
        host=bind_host,
        port=8000,
        ssl=_ssl_context(),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
