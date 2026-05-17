"""Discovery Engine — subnet scan via SNMP, fingerprinting, and Device upsert."""

from __future__ import annotations

import asyncio
import ipaddress
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, settings as default_settings
from app.models.device import Device
from app.services.snmp.engine import SNMPEngine
from app.services.snmp.poller import SNMPCredential

# ---------------------------------------------------------------------------
# OID prefixes for vendor detection
# ---------------------------------------------------------------------------
_CISCO_OID_PREFIX = "1.3.6.1.4.1.9.1."
_JUNIPER_OID_PREFIX = "1.3.6.1.4.1.2636.1.1.1"
_ARISTA_OID_PREFIX = "1.3.6.1.4.1.30065"


@dataclass(slots=True)
class DiscoveredDevice:
    """Device found during a subnet scan."""

    ip: str
    sys_descr: str
    sys_name: str
    sys_object_id: str
    vendor: str       # "cisco" | "juniper" | "arista" | "unknown"
    os_type: str      # "ios-xr" | "ios-xe" | "nx-os" | "junos" | "unknown"


def fingerprint(sys_descr: str, sys_object_id: str) -> tuple[str, str]:
    """Pure function: detect vendor and OS type from sysDescr and sysObjectID.

    Returns (vendor, os_type) strings.
    """
    descr = sys_descr.upper()
    oid = sys_object_id.strip()

    # Juniper — check before Cisco to avoid false positives on OID prefix length
    if "JUNOS" in descr or oid.startswith(_JUNIPER_OID_PREFIX):
        return ("juniper", "junos")

    # Arista
    if "ARISTA" in descr or oid.startswith(_ARISTA_OID_PREFIX):
        return ("arista", "eos")

    # Cisco variants — check most specific first
    is_cisco_oid = oid.startswith(_CISCO_OID_PREFIX)

    if "IOS XR" in descr or (is_cisco_oid and "IOS XR" in descr):
        return ("cisco", "ios-xr")

    if "NX-OS" in descr or "NEXUS" in descr:
        return ("cisco", "nx-os")

    if "IOS-XE" in descr or ("IOS SOFTWARE" in descr and "IOS-XE" in descr):
        return ("cisco", "ios-xe")

    # Generic Cisco (matched by OID prefix only — OS unknown)
    if is_cisco_oid or "CISCO" in descr:
        return ("cisco", "unknown")

    return ("unknown", "unknown")


class DiscoveryEngine:
    """Scans subnets via SNMP, fingerprints devices, and persists them."""

    def __init__(
        self,
        snmp_engine: SNMPEngine,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._snmp = snmp_engine
        self._session_factory = session_factory
        self._settings = settings or default_settings

    async def scan_subnet(
        self, cidr: str, communities: list[str]
    ) -> list[DiscoveredDevice]:
        """Iterate all host addresses in cidr, probe each community, return found devices."""
        network = ipaddress.ip_network(cidr, strict=False)
        sem = asyncio.Semaphore(self._settings.discovery_chunk_size)
        discovered: list[DiscoveredDevice] = []

        async def _probe(ip: str) -> None:
            async with sem:
                device = await self._try_communities(ip, communities)
                if device:
                    discovered.append(device)

        hosts = [str(h) for h in network.hosts()]
        logger.info("Discovery scan starting: {} ({} hosts)", cidr, len(hosts))
        await asyncio.gather(*[_probe(h) for h in hosts], return_exceptions=True)
        logger.info("Discovery scan complete: {} devices found in {}", len(discovered), cidr)
        return discovered

    async def persist(self, devices: list[DiscoveredDevice]) -> int:
        """Upsert DiscoveredDevices into the Device table by ip_address. Returns new device count."""
        if not devices:
            return 0
        new_count = 0
        async with self._session_factory() as session:
            for dev in devices:
                new_count += await _upsert_device(session, dev)
            await session.commit()
        return new_count

    async def ping(self, host: str) -> bool:
        """Non-root ICMP ping using the system ping binary."""
        timeout = str(self._settings.discovery_timeout)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", timeout, host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception as exc:  # noqa: BLE001
            logger.debug("ping({}) failed: {}", host, exc)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _try_communities(
        self, ip: str, communities: list[str]
    ) -> DiscoveredDevice | None:
        """Try each community string until one succeeds. Returns DiscoveredDevice or None."""
        for community in communities:
            cred = SNMPCredential(
                version="v2c",
                community=community,
                timeout=float(self._settings.discovery_timeout),
                retries=0,
            )
            info = await self._snmp.get_system_info(ip, cred)
            if not info:
                continue
            sys_descr = info.get("sysDescr", "")
            sys_object_id = info.get("sysObjectID", "")
            vendor, os_type = fingerprint(sys_descr, sys_object_id)
            logger.debug("Discovered {}: vendor={} os={}", ip, vendor, os_type)
            return DiscoveredDevice(
                ip=ip,
                sys_descr=sys_descr,
                sys_name=info.get("sysName", ""),
                sys_object_id=sys_object_id,
                vendor=vendor,
                os_type=os_type,
            )
        return None


async def _upsert_device(session: AsyncSession, dev: DiscoveredDevice) -> int:
    """Insert or update a Device row. Returns 1 if new, 0 if updated."""
    stmt = select(Device).where(Device.ip_address == dev.ip)
    result = await session.execute(stmt)
    existing: Device | None = result.scalar_one_or_none()

    if existing:
        existing.vendor = dev.vendor
        existing.os_type = dev.os_type
        existing.updated_at = datetime.now(timezone.utc)
        if dev.sys_name and existing.name == existing.ip_address:
            existing.name = dev.sys_name
        return 0

    new_device = Device(
        id=uuid.uuid4(),
        name=dev.sys_name or dev.ip,
        ip_address=dev.ip,
        device_type="router",       # best-effort default
        vendor=dev.vendor,
        os_type=dev.os_type,
        status="discovered",
        snmp_enabled=True,
    )
    session.add(new_device)
    return 1
