"""Production server launcher with optional TLS 1.3 HTTPS."""

from __future__ import annotations

import datetime as dt
import ipaddress
import ssl
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

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

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.now(dt.UTC))
        .not_valid_after(dt.datetime.now(dt.UTC) + dt.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.DNSName("app"),
                    x509.DNSName("frontend"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    key_file.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


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
