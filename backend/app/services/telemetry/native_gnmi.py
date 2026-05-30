"""Lab-ready interfaces for a future native gNMI adapter.

No protobuf/gRPC dependency is imported here on purpose. Production native gNMI
should generate stubs from openconfig/gnmi proto files and inject an adapter that
implements this contract.
"""

from __future__ import annotations

import uuid as _uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

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
    device_id: _uuid.UUID = field(default_factory=_uuid.uuid4)
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


@dataclass(frozen=True, slots=True)
class GnmiUpdate:
    """Single normalized update emitted by an adapter, pre-schema conversion."""

    path: str
    value: float
    timestamp: datetime
    labels: dict[str, str] = field(default_factory=dict)


class StubNativeGnmiAdapter:
    """Deterministic in-process adapter for lab/tests without real gRPC.

    Yields a finite, replayable sequence of updates so callers can exercise
    downstream telemetry processing without standing up an actual gNMI server.
    Production code must replace this with a protobuf/gRPC implementation.
    """

    name = "stub"

    def __init__(self, updates: list[GnmiUpdate]) -> None:
        self._updates = list(updates)

    async def subscribe(
        self, config: GnmiSubscriptionConfig
    ) -> AsyncIterator[TelemetrySampleIngest]:
        for u in self._updates:
            yield TelemetrySampleIngest(  # type: ignore[call-arg]  # pydantic v2 stub issue with Field() defaults
                device_id=config.device_id,
                path=u.path,
                value=u.value,
                timestamp=u.timestamp,
                labels=u.labels or None,
            )


def make_lab_subscription(target: str, paths: tuple[str, ...]) -> GnmiSubscriptionConfig:
    """Convenience factory: builds a lab-safe mTLS-required subscription."""
    return GnmiSubscriptionConfig(
        target=target,
        paths=paths,
        mode="stream",
        sample_interval_ns=10_000_000_000,
        tls=GnmiTLSConfig(
            ca_cert=Path("/etc/nms/tls/ca.pem"),
            client_cert=Path("/etc/nms/tls/client.pem"),
            client_key=Path("/etc/nms/tls/client.key"),
            require_mutual_tls=True,
        ),
    )


def build_stub_from_paths(
    paths: tuple[str, ...],
    *,
    start_value: float = 0.0,
    step: float = 1.0,
) -> StubNativeGnmiAdapter:
    """Construct a stub adapter with one update per requested path."""
    now = datetime.now(UTC)
    updates = [
        GnmiUpdate(path=p, value=start_value + i * step, timestamp=now)
        for i, p in enumerate(paths)
    ]
    return StubNativeGnmiAdapter(updates)
