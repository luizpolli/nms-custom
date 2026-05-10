"""IOS version detection, parsing, and EOL/EOS tracking.

Supported platforms: IOS XR, IOS XE, NX-OS, classic IOS.
EOL/EOS data is currently an in-memory dict — see TODO below for live feed.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.credential import Credential
from app.models.device import Device
from app.models.ios_version import IOSVersion
from app.services.ssh.client import SSHClient, SSHCredential

# ---------------------------------------------------------------------------
# EOL / EOS registry (in-memory placeholder)
# TODO: replace with live Cisco EOX / PSIRT API feed
# ---------------------------------------------------------------------------

_EOL_VERSIONS: dict[str, bool] = {
    "6.1.4": True,
    "6.2.3": True,
    "6.4.2": True,
    "16.6.1": True,
    "15.6(2)T": True,
    "7.0(3)I7(6)": True,
}

_EOS_VERSIONS: dict[str, bool] = {
    "6.1.4": True,
    "6.2.3": True,
    "15.6(2)T": True,
}

# ---------------------------------------------------------------------------
# Regex patterns per platform
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, dict[str, str]] = {
    "ios-xr": {
        "version": r"Cisco IOS XR Software.*?Version\s+([^\s,]+)",
        "image_file": r"image file is\s+\"([^\"]+)\"",
        "platform": r"cisco\s+(\S+)\s+\(",
        "boot_image": r"BOOT variable\s*=\s*(\S+)",
        "uptime": r"uptime is\s+(.*?)(?:\n|$)",
    },
    "ios-xe": {
        "version": r"Cisco IOS XE Software.*?Version\s+([^\s,]+)",
        "image_file": r"System image file is\s+\"([^\"]+)\"",
        "platform": r"cisco\s+(\S+)\s+\(",
        "boot_image": r"BOOT path-list\s*:\s*(\S+)",
        "uptime": r"uptime is\s+(.*?)(?:\n|$)",
    },
    "nxos": {
        "version": r"NXOS:\s+version\s+([^\s]+)",
        "image_file": r"NXOS image file is:\s+(\S+)",
        "platform": r"Hardware\s*\n\s*cisco\s+(\S+)",
        "boot_image": r"kickstart:\s+(\S+)",
        "uptime": r"Kernel uptime is\s+(.*?)(?:\n|$)",
    },
    "ios": {
        "version": r"Cisco IOS Software.*?Version\s+([^\s,]+)",
        "image_file": r"System image file is\s+\"([^\"]+)\"",
        "platform": r"cisco\s+(\S+)\s+\(",
        "boot_image": r"BOOT variable\s*=\s*(\S+)",
        "uptime": r"uptime is\s+(.*?)(?:\n|$)",
    },
}


def _detect_os_type(output: str) -> str:
    """Heuristically determine the platform OS from show version output."""
    if "IOS XR" in output:
        return "ios-xr"
    if "IOS XE" in output or "IOS-XE" in output:
        return "ios-xe"
    if "NX-OS" in output or "NXOS" in output:
        return "nxos"
    return "ios"


def _parse_uptime_hours(uptime_str: str) -> int | None:
    """Convert a Cisco uptime string into total hours (best-effort)."""
    hours = 0
    m = re.search(r"(\d+)\s+week", uptime_str)
    if m:
        hours += int(m.group(1)) * 7 * 24
    m = re.search(r"(\d+)\s+day", uptime_str)
    if m:
        hours += int(m.group(1)) * 24
    m = re.search(r"(\d+)\s+hour", uptime_str)
    if m:
        hours += int(m.group(1))
    return hours if hours else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_show_version(output: str, os_type: str) -> dict:
    """Pure parser: extract version fields from show version output.

    Returns a dict with keys: version, image_file, platform, boot_image, uptime_hours.
    Values are None when the pattern does not match.
    """
    patterns = _PATTERNS.get(os_type, _PATTERNS["ios"])
    result: dict[str, str | int | None] = {}

    for field, pattern in patterns.items():
        m = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
        if field == "uptime":
            result["uptime_hours"] = _parse_uptime_hours(m.group(1)) if m else None
        else:
            result[field] = m.group(1).strip() if m else None

    return result


class IOSVersionManager:
    """Detects and persists IOS version information for network devices."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def detect_version(self, device: Device, credential: Credential) -> IOSVersion:
        """Run `show version` over SSH, parse the output, and persist a new IOSVersion row."""
        ssh_cred = SSHCredential(
            host=device.ip_address,
            username=credential.username,
            password=credential.auth_key if not credential.auth_key.startswith("-----") else None,
            private_key=credential.auth_key if credential.auth_key.startswith("-----") else None,
        )

        logger.info("detect_version host={} device_id={}", device.ip_address, device.id)

        async with SSHClient(ssh_cred) as client:
            result = await client.run("show version", timeout=30)

        if not result.success:
            raise RuntimeError(
                f"show version failed on {device.ip_address}: {result.error or result.stderr}"
            )

        os_type = device.os_type or _detect_os_type(result.stdout)
        parsed = parse_show_version(result.stdout, os_type)
        logger.debug("parsed show version for {}: {}", device.ip_address, parsed)

        version_str: str | None = parsed.get("version")  # type: ignore[assignment]
        is_eol, is_eos = await self.check_eol(version_str or "", os_type)

        ios_ver = IOSVersion(
            id=uuid.uuid4(),
            device_id=device.id,
            version=version_str,
            image_file=parsed.get("image_file"),  # type: ignore[arg-type]
            platform=parsed.get("platform"),  # type: ignore[arg-type]
            boot_image=parsed.get("boot_image"),  # type: ignore[arg-type]
            uptime_hours=parsed.get("uptime_hours"),  # type: ignore[arg-type]
            is_eol=is_eol,
            is_eos=is_eos,
            created_at=datetime.now(),
        )

        async with self._sf() as session:
            session.add(ios_ver)
            await session.commit()
            logger.info(
                "IOSVersion persisted id={} version={} device_id={}",
                ios_ver.id,
                ios_ver.version,
                device.id,
            )

        return ios_ver

    async def check_eol(self, version: str, platform: str) -> tuple[bool, bool]:
        """Return (is_eol, is_eos) for the given version string.

        Currently uses an in-memory dict.
        TODO: integrate with Cisco EOX / PSIRT API for live data.
        """
        is_eol = _EOL_VERSIONS.get(version, False)
        is_eos = _EOS_VERSIONS.get(version, False)
        logger.debug("check_eol version={} platform={} eol={} eos={}", version, platform, is_eol, is_eos)
        return is_eol, is_eos
