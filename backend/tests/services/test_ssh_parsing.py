"""Unit tests for SSH parsing helpers.

Tests parse_show_version and SSHCredential. No live SSH connections.
"""

from __future__ import annotations

import pytest

from app.services.ios.version_manager import parse_show_version
from app.services.ssh.client import SSHCredential

# ---------------------------------------------------------------------------
# Fixtures — sample show version outputs
# ---------------------------------------------------------------------------

IOS_XR_OUTPUT = """
Cisco IOS XR Software, Version 7.3.2
Copyright (c) 2013-2021 by Cisco Systems, Inc.

Build Information:
 Built By     : ahoang
 image file is "disk0:asr9k-os-mbi-7.3.2/0x100305/mbiasr9k-rp.vm"
 Boot variable = disk0:asr9k-os-mbi-7.3.2/0x100305/mbiasr9k-rp.vm
cisco ASR9010 (RP64) processor
 uptime is 3 weeks, 2 days, 4 hours, 15 minutes
"""

IOS_XE_OUTPUT = """
Cisco IOS XE Software, Version 16.12.4
Cisco IOS Software [Gibraltar], ASR920 Software (PPC_LINUX_IOSD-UNIVERSALK9_NPE-M), Version 16.12.4, RELEASE SOFTWARE (fc5)

System image file is "flash:asr920-universalk9_npe.16.12.04.SPA.bin"
cisco ASR920 (Freescale P2020) processor
uptime is 1 week, 3 days, 7 hours, 44 minutes
"""

NXOS_OUTPUT = """
Cisco Nexus Operating System (NX-OS) Software
NXOS: version 9.3(7)
NXOS image file is: bootflash:///nxos.9.3.7.bin
Hardware
  cisco Nexus9000 C93180YC-EX chassis
Kernel uptime is 0 week(s), 5 day(s), 10 hour(s), 22 minute(s)
"""

CLASSIC_IOS_OUTPUT = """
Cisco IOS Software, Version 15.6(2)T, RELEASE SOFTWARE (fc2)
Technical Support: http://www.cisco.com/techsupport

System image file is "flash0:c2901-universalk9-mz.SPA.156-2.T.bin"
cisco CISCO2901/K9 (revision 1.0)
Router uptime is 45 weeks, 1 day, 3 hours, 5 minutes
"""


# ---------------------------------------------------------------------------
# parse_show_version — IOS XR
# ---------------------------------------------------------------------------

class TestParseShowVersionIOSXR:
    def test_version_extracted(self) -> None:
        result = parse_show_version(IOS_XR_OUTPUT, "ios-xr")
        assert result["version"] == "7.3.2"

    def test_image_file_extracted(self) -> None:
        result = parse_show_version(IOS_XR_OUTPUT, "ios-xr")
        assert result["image_file"] == "disk0:asr9k-os-mbi-7.3.2/0x100305/mbiasr9k-rp.vm"

    def test_platform_extracted(self) -> None:
        result = parse_show_version(IOS_XR_OUTPUT, "ios-xr")
        assert result["platform"] == "ASR9010"

    def test_boot_image_extracted(self) -> None:
        result = parse_show_version(IOS_XR_OUTPUT, "ios-xr")
        assert result["boot_image"] is not None

    def test_uptime_hours(self) -> None:
        result = parse_show_version(IOS_XR_OUTPUT, "ios-xr")
        # 3 weeks (504h) + 2 days (48h) + 4h = 556
        assert result["uptime_hours"] == 556


# ---------------------------------------------------------------------------
# parse_show_version — IOS XE
# ---------------------------------------------------------------------------

class TestParseShowVersionIOSXE:
    def test_version_extracted(self) -> None:
        result = parse_show_version(IOS_XE_OUTPUT, "ios-xe")
        assert result["version"] == "16.12.4"

    def test_image_file_extracted(self) -> None:
        result = parse_show_version(IOS_XE_OUTPUT, "ios-xe")
        assert "asr920" in result["image_file"].lower()

    def test_platform_extracted(self) -> None:
        result = parse_show_version(IOS_XE_OUTPUT, "ios-xe")
        assert result["platform"] == "ASR920"

    def test_uptime_hours(self) -> None:
        result = parse_show_version(IOS_XE_OUTPUT, "ios-xe")
        # 1 week (168h) + 3 days (72h) + 7h = 247
        assert result["uptime_hours"] == 247


# ---------------------------------------------------------------------------
# parse_show_version — NX-OS
# ---------------------------------------------------------------------------

class TestParseShowVersionNXOS:
    def test_version_extracted(self) -> None:
        result = parse_show_version(NXOS_OUTPUT, "nxos")
        assert result["version"] == "9.3(7)"

    def test_image_file_extracted(self) -> None:
        result = parse_show_version(NXOS_OUTPUT, "nxos")
        assert "nxos.9.3.7.bin" in result["image_file"]

    def test_platform_extracted(self) -> None:
        result = parse_show_version(NXOS_OUTPUT, "nxos")
        assert result["platform"] == "Nexus9000"

    def test_uptime_hours(self) -> None:
        result = parse_show_version(NXOS_OUTPUT, "nxos")
        # 5 days (120h) + 10h = 130
        assert result["uptime_hours"] == 130


# ---------------------------------------------------------------------------
# parse_show_version — classic IOS
# ---------------------------------------------------------------------------

class TestParseShowVersionClassicIOS:
    def test_version_extracted(self) -> None:
        result = parse_show_version(CLASSIC_IOS_OUTPUT, "ios")
        assert result["version"] == "15.6(2)T"

    def test_image_file_extracted(self) -> None:
        result = parse_show_version(CLASSIC_IOS_OUTPUT, "ios")
        assert "c2901" in result["image_file"]

    def test_uptime_hours(self) -> None:
        result = parse_show_version(CLASSIC_IOS_OUTPUT, "ios")
        # 45 weeks (7560h) + 1 day (24h) + 3h = 7587
        assert result["uptime_hours"] == 7587


# ---------------------------------------------------------------------------
# parse_show_version — missing fields return None
# ---------------------------------------------------------------------------

class TestParseShowVersionMissingFields:
    def test_empty_output_returns_none_values(self) -> None:
        result = parse_show_version("", "ios-xr")
        assert result["version"] is None
        assert result["image_file"] is None
        assert result["uptime_hours"] is None


# ---------------------------------------------------------------------------
# SSHCredential
# ---------------------------------------------------------------------------

class TestSSHCredential:
    def test_defaults(self) -> None:
        cred = SSHCredential(host="10.0.0.1", username="admin")
        assert cred.port == 22
        assert cred.connect_timeout == 10
        assert cred.password is None
        assert cred.private_key is None
        assert cred.known_hosts_path is None

    def test_password_set(self) -> None:
        cred = SSHCredential(host="10.0.0.1", username="admin", password="secret")
        assert cred.password == "secret"

    def test_private_key_set(self) -> None:
        cred = SSHCredential(host="10.0.0.1", username="admin", private_key="/root/.ssh/id_rsa")
        assert cred.private_key == "/root/.ssh/id_rsa"

    def test_custom_port(self) -> None:
        cred = SSHCredential(host="10.0.0.1", username="admin", port=2222)
        assert cred.port == 2222

    def test_host_required(self) -> None:
        """SSHCredential must have a host (no default)."""
        with pytest.raises(TypeError):
            SSHCredential(username="admin")  # type: ignore[call-arg]

    def test_username_required(self) -> None:
        with pytest.raises(TypeError):
            SSHCredential(host="10.0.0.1")  # type: ignore[call-arg]
