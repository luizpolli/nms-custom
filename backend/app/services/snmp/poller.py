"""Async SNMP poller — get / get-next / walk against a single device.

Wraps pysnmp's high-level v3arch async API (the lextudio fork). We deliberately
expose a small surface (``get``, ``walk``, ``bulk_walk``) returning plain
``dict[str, str]`` (OID -> value) so the rest of the system never imports pysnmp
types directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

try:
    from pysnmp.hlapi.v3arch.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        UsmUserData,
        bulk_walk_cmd,
        get_cmd,
        walk_cmd,
    )
except ImportError:  # pragma: no cover — surface the real error at runtime
    CommunityData = ContextData = ObjectIdentity = ObjectType = None  # type: ignore[assignment]
    SnmpEngine = UdpTransportTarget = UsmUserData = None  # type: ignore[assignment]
    bulk_walk_cmd = get_cmd = walk_cmd = None  # type: ignore[assignment]


@dataclass(slots=True)
class SNMPCredential:
    """SNMP credentials abstraction supporting v1/v2c/v3."""

    version: str = "v2c"
    community: str = "public"
    # SNMPv3
    user: str | None = None
    auth_protocol: str | None = None  # "MD5" | "SHA" | "SHA256" | "SHA512" | None
    auth_key: str | None = None
    priv_protocol: str | None = None  # "DES" | "AES128" | "AES192" | "AES256" | None
    priv_key: str | None = None
    # Transport
    port: int = 161
    timeout: float = 5.0
    retries: int = 1


@dataclass(slots=True)
class SNMPResult:
    """Result of an SNMP operation."""

    host: str
    success: bool
    varbinds: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def _auth_data(cred: SNMPCredential) -> Any:
    """Build the pysnmp auth data object from credentials."""
    if cred.version in ("v1", "v2c"):
        return CommunityData(cred.community, mpModel=0 if cred.version == "v1" else 1)

    if cred.version != "v3":
        raise ValueError(f"Unsupported SNMP version: {cred.version}")
    if not cred.user:
        raise ValueError("SNMPv3 requires a user")

    # Lazy import to avoid hard-coding protocol OIDs at module import
    from pysnmp.hlapi.v3arch.asyncio import (
        usmHMACMD5AuthProtocol,
        usmHMACSHAAuthProtocol,
        usmHMAC128SHA224AuthProtocol,  # noqa: F401
        usmHMAC192SHA256AuthProtocol,
        usmHMAC384SHA512AuthProtocol,
        usmDESPrivProtocol,
        usmAesCfb128Protocol,
        usmAesCfb192Protocol,
        usmAesCfb256Protocol,
        usmNoAuthProtocol,
        usmNoPrivProtocol,
    )

    auth_map = {
        None: usmNoAuthProtocol,
        "MD5": usmHMACMD5AuthProtocol,
        "SHA": usmHMACSHAAuthProtocol,
        "SHA256": usmHMAC192SHA256AuthProtocol,
        "SHA512": usmHMAC384SHA512AuthProtocol,
    }
    priv_map = {
        None: usmNoPrivProtocol,
        "DES": usmDESPrivProtocol,
        "AES128": usmAesCfb128Protocol,
        "AES192": usmAesCfb192Protocol,
        "AES256": usmAesCfb256Protocol,
    }
    return UsmUserData(
        cred.user,
        authKey=cred.auth_key,
        privKey=cred.priv_key,
        authProtocol=auth_map.get(cred.auth_protocol, usmNoAuthProtocol),
        privProtocol=priv_map.get(cred.priv_protocol, usmNoPrivProtocol),
    )


class SNMPPoller:
    """Async SNMP poller. Reuses a single ``SnmpEngine`` instance for efficiency."""

    def __init__(self) -> None:
        if SnmpEngine is None:
            raise RuntimeError(
                "pysnmp-lextudio is not installed — pip install pysnmp-lextudio"
            )
        self._engine = SnmpEngine()

    async def _transport(self, host: str, cred: SNMPCredential) -> Any:
        return await UdpTransportTarget.create(
            (host, cred.port), timeout=cred.timeout, retries=cred.retries
        )

    async def get(
        self, host: str, oids: list[str], cred: SNMPCredential
    ) -> SNMPResult:
        """SNMP GET on one or more OIDs. Returns OID->value map."""
        try:
            transport = await self._transport(host, cred)
            obj_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
            err_ind, err_status, err_idx, varbinds = await get_cmd(
                self._engine, _auth_data(cred), transport, ContextData(), *obj_types
            )
            if err_ind:
                return SNMPResult(host=host, success=False, error=str(err_ind))
            if err_status:
                return SNMPResult(
                    host=host, success=False,
                    error=f"{err_status.prettyPrint()} at {err_idx}",
                )
            result = {str(vb[0]): str(vb[1]) for vb in varbinds}
            return SNMPResult(host=host, success=True, varbinds=result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("SNMP GET failed for {}: {}", host, exc)
            return SNMPResult(host=host, success=False, error=str(exc))

    async def walk(
        self, host: str, oid: str, cred: SNMPCredential, max_rows: int = 10_000
    ) -> SNMPResult:
        """SNMP WALK from a base OID. Returns OID->value map for the subtree."""
        result: dict[str, str] = {}
        try:
            transport = await self._transport(host, cred)
            iterator = walk_cmd(
                self._engine, _auth_data(cred), transport, ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
            )
            async for err_ind, err_status, err_idx, varbinds in iterator:
                if err_ind:
                    return SNMPResult(host=host, success=False, error=str(err_ind))
                if err_status:
                    return SNMPResult(
                        host=host, success=False,
                        error=f"{err_status.prettyPrint()} at {err_idx}",
                    )
                for vb in varbinds:
                    result[str(vb[0])] = str(vb[1])
                    if len(result) >= max_rows:
                        return SNMPResult(host=host, success=True, varbinds=result)
            return SNMPResult(host=host, success=True, varbinds=result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("SNMP WALK failed for {} oid={}: {}", host, oid, exc)
            return SNMPResult(host=host, success=False, error=str(exc), varbinds=result)

    async def bulk_walk(
        self,
        host: str,
        oid: str,
        cred: SNMPCredential,
        non_repeaters: int = 0,
        max_repetitions: int = 25,
        max_rows: int = 10_000,
    ) -> SNMPResult:
        """SNMP GETBULK walk — much faster than WALK on large tables (v2c/v3 only)."""
        if cred.version == "v1":
            return await self.walk(host, oid, cred, max_rows=max_rows)
        result: dict[str, str] = {}
        try:
            transport = await self._transport(host, cred)
            iterator = bulk_walk_cmd(
                self._engine, _auth_data(cred), transport, ContextData(),
                non_repeaters, max_repetitions,
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
            )
            async for err_ind, err_status, err_idx, varbinds in iterator:
                if err_ind:
                    return SNMPResult(host=host, success=False, error=str(err_ind))
                if err_status:
                    return SNMPResult(
                        host=host, success=False,
                        error=f"{err_status.prettyPrint()} at {err_idx}",
                    )
                for vb in varbinds:
                    result[str(vb[0])] = str(vb[1])
                    if len(result) >= max_rows:
                        return SNMPResult(host=host, success=True, varbinds=result)
            return SNMPResult(host=host, success=True, varbinds=result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("SNMP BULK_WALK failed for {} oid={}: {}", host, oid, exc)
            return SNMPResult(host=host, success=False, error=str(exc), varbinds=result)

    def close(self) -> None:
        """Tear down the SNMP engine."""
        try:
            self._engine.close_dispatcher()
        except Exception:  # noqa: BLE001
            pass
