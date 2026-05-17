"""Lab-ready interfaces for a future native gNMI adapter.

No protobuf/gRPC dependency is imported here on purpose. Production native gNMI
should generate stubs from openconfig/gnmi proto files and inject an adapter that
implements this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Protocol

from app.schemas.telemetry import TelemetrySampleIngest


@dataclass(frozen=True, slots=True)
class GnmiTLSConfig:
    """TLS/mTLS material required by a native gNMI collector."""

    ca_cert: Path
    client_cert: Path | None = None
    client_key: Path | None = None
    server_name: str | None = None
    require_mutual_tls: bool = True


@dataclass(frozen=True, slots=True)
class GnmiSubscriptionConfig:
    target: str
    port: int = 57400
    paths: tuple[str, ...] = ()
    mode: str = "stream"
    sample_interval_ns: int | None = None
    tls: GnmiTLSConfig | None = None


class NativeGnmiAdapter(Protocol):
    """Protocol future protobuf/gRPC implementations must satisfy."""

    async def subscribe(self, config: GnmiSubscriptionConfig) -> AsyncIterator[TelemetrySampleIngest]:
        """Yield normalized telemetry samples from a gNMI Subscribe RPC."""
        ...


def validate_native_gnmi_tls(config: GnmiSubscriptionConfig) -> None:
    """Fail fast on unsafe native gNMI lab configs."""
    if config.tls is None:
        raise ValueError("Native gNMI requires TLS configuration")
    if config.tls.require_mutual_tls and (not config.tls.client_cert or not config.tls.client_key):
        raise ValueError("Native gNMI mTLS requires client_cert and client_key")
