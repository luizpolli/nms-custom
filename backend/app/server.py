"""Production server launcher with optional TLS 1.3 HTTPS."""

from __future__ import annotations

import ssl

import uvicorn

from app.config import settings


def _ssl_context() -> ssl.SSLContext | None:
    if not settings.https_enabled:
        return None
    if not settings.tls_cert_file or not settings.tls_key_file:
        raise RuntimeError("HTTPS enabled but TLS_CERT_FILE/TLS_KEY_FILE are not configured")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3 if settings.tls_min_version == "TLSv1.3" else ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(settings.tls_cert_file, settings.tls_key_file)
    if settings.tls_ca_file:
        ctx.load_verify_locations(settings.tls_ca_file)
    return ctx


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
