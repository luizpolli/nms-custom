"""Async SNMP trap receiver — listens on UDP/162 (configurable) and dispatches
incoming traps to a callback for alarm correlation / syslog forwarding.

Use:

    receiver = SNMPTrapReceiver(communities=["public"])
    receiver.on_trap(my_handler)
    await receiver.start()

The handler receives a :class:`TrapEvent` instance.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from loguru import logger

try:
    from pysnmp.carrier.asyncio.dgram import udp
    from pysnmp.entity import config, engine
    from pysnmp.entity.rfc3413 import ntfrcv
    from pysnmp.proto.rfc1902 import OctetString
except ImportError:  # pragma: no cover
    config = engine = udp = ntfrcv = OctetString = None  # type: ignore[assignment]


TrapHandler = Callable[["TrapEvent"], Awaitable[None] | None]

# Protocol names mirror app.services.snmp.poller so credentials read the same
# everywhere. Validation happens at parse time without importing pysnmp.
AUTH_PROTOCOLS = ("MD5", "SHA", "SHA224", "SHA256", "SHA384", "SHA512")
PRIV_PROTOCOLS = ("DES", "3DES", "AES128", "AES192", "AES256")

_ENGINE_ID_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}){5,32}$")


@dataclass(slots=True)
class TrapV3User:
    """USM user accepted by the trap receiver.

    ``engine_id`` is the hex snmpEngineID of the SENDING device. SNMPv3 TRAP
    PDUs are authoritative on the sender side, so the receiver needs the
    sender's engine ID to localize keys; INFORM PDUs do not require it.
    """

    user: str
    auth_protocol: str | None = None
    auth_key: str | None = None
    priv_protocol: str | None = None
    priv_key: str | None = None
    engine_id: str | None = None


def parse_trap_v3_users(raw: str) -> list[TrapV3User]:
    """Parse the TRAP_V3_USERS setting (JSON list of user objects).

    Example::

        [{"user": "nms-trap", "auth_protocol": "SHA256", "auth_key": "...",
          "priv_protocol": "AES128", "priv_key": "...",
          "engine_id": "80000009030000112233445566"}]
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"TRAP_V3_USERS is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise ValueError("TRAP_V3_USERS must be a JSON list of user objects")

    users: list[TrapV3User] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not entry.get("user"):
            raise ValueError(f"TRAP_V3_USERS[{index}] must be an object with a 'user' field")
        auth_protocol = _normalize_protocol(entry.get("auth_protocol"))
        priv_protocol = _normalize_protocol(entry.get("priv_protocol"))
        if auth_protocol is not None and auth_protocol not in AUTH_PROTOCOLS:
            raise ValueError(
                f"TRAP_V3_USERS[{index}] auth_protocol {auth_protocol!r} not in {AUTH_PROTOCOLS}"
            )
        if priv_protocol is not None and priv_protocol not in PRIV_PROTOCOLS:
            raise ValueError(
                f"TRAP_V3_USERS[{index}] priv_protocol {priv_protocol!r} not in {PRIV_PROTOCOLS}"
            )
        if entry.get("priv_key") and not entry.get("auth_key"):
            raise ValueError(
                f"TRAP_V3_USERS[{index}]: priv_key requires auth_key (USM authPriv)"
            )
        engine_id = entry.get("engine_id")
        if engine_id is not None and not _ENGINE_ID_RE.fullmatch(str(engine_id)):
            raise ValueError(
                f"TRAP_V3_USERS[{index}] engine_id must be 5-32 hex octets, got {engine_id!r}"
            )
        users.append(
            TrapV3User(
                user=str(entry["user"]),
                auth_protocol=auth_protocol,
                auth_key=entry.get("auth_key"),
                priv_protocol=priv_protocol,
                priv_key=entry.get("priv_key"),
                engine_id=str(engine_id) if engine_id is not None else None,
            )
        )
    return users


def _normalize_protocol(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value).strip().upper()


def _usm_protocols(user: TrapV3User) -> tuple[tuple, tuple]:
    """Map protocol names to pysnmp USM OIDs (requires pysnmp installed)."""
    auth_map = {
        None: config.USM_AUTH_NONE,
        "MD5": config.USM_AUTH_HMAC96_MD5,
        "SHA": config.USM_AUTH_HMAC96_SHA,
        "SHA224": config.USM_AUTH_HMAC128_SHA224,
        "SHA256": config.USM_AUTH_HMAC192_SHA256,
        "SHA384": config.USM_AUTH_HMAC256_SHA384,
        "SHA512": config.USM_AUTH_HMAC384_SHA512,
    }
    priv_map = {
        None: config.USM_PRIV_NONE,
        "DES": config.USM_PRIV_CBC56_DES,
        "3DES": config.USM_PRIV_CBC168_3DES,
        "AES128": config.USM_PRIV_CFB128_AES,
        "AES192": config.USM_PRIV_CFB192_AES,
        "AES256": config.USM_PRIV_CFB256_AES,
    }
    return auth_map[user.auth_protocol], priv_map[user.priv_protocol]


@dataclass(slots=True)
class TrapEvent:
    """A single received SNMP trap."""

    source_host: str
    source_port: int
    community: str | None
    trap_oid: str | None
    varbinds: dict[str, str] = field(default_factory=dict)
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SNMPTrapReceiver:
    """Listens for SNMP traps on a UDP port and dispatches them to handlers."""

    def __init__(
        self,
        bind_host: str = "127.0.0.1",
        bind_port: int = 162,
        communities: list[str] | None = None,
        v3_users: list[TrapV3User] | None = None,
    ) -> None:
        if engine is None:
            raise RuntimeError("pysnmp-lextudio is not installed")
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.communities = communities or ["public"]
        self.v3_users = list(v3_users or [])
        self._engine: object | None = None
        self._handlers: list[TrapHandler] = []
        self._loop_task: asyncio.Task[None] | None = None

    def on_trap(self, handler: TrapHandler) -> None:
        """Register a callback (sync or async) for received traps."""
        self._handlers.append(handler)

    async def start(self) -> None:
        """Bind socket and begin listening. Idempotent."""
        if self._engine is not None:
            return
        snmp_engine = engine.SnmpEngine()

        # Transport
        config.add_transport(
            snmp_engine,
            udp.DOMAIN_NAME + (1,),
            udp.UdpTransport().open_server_mode((self.bind_host, self.bind_port)),
        )

        # Accept any of the configured communities
        for idx, community in enumerate(self.communities, start=1):
            config.add_v1_system(snmp_engine, f"comm-{idx}", community)

        # SNMPv3 USM users
        self._register_v3_users(snmp_engine)

        ntfrcv.NotificationReceiver(snmp_engine, self._on_pysnmp_trap)
        self._engine = snmp_engine
        # pysnmp's dispatcher runs in the current event loop after first trap
        snmp_engine.transport_dispatcher.job_started(1)
        logger.info(
            "SNMP trap receiver listening on {}:{}", self.bind_host, self.bind_port
        )

    def _register_v3_users(self, snmp_engine: object) -> None:
        """Register configured USM users on the receiving engine."""
        for user in self.v3_users:
            auth_protocol, priv_protocol = _usm_protocols(user)
            kwargs: dict[str, object] = {}
            if user.engine_id:
                kwargs["securityEngineId"] = OctetString(hexValue=user.engine_id)
            else:
                logger.warning(
                    "SNMPv3 user '{}' has no engine_id — v3 TRAP PDUs from "
                    "authoritative senders will be dropped; only INFORMs will "
                    "be accepted for this user",
                    user.user,
                )
            config.add_v3_user(
                snmp_engine,
                user.user,
                authProtocol=auth_protocol,
                authKey=user.auth_key,
                privProtocol=priv_protocol,
                privKey=user.priv_key,
                **kwargs,
            )
            logger.info(
                "SNMPv3 USM user '{}' registered (auth={} priv={} engine_id={})",
                user.user,
                user.auth_protocol or "none",
                user.priv_protocol or "none",
                user.engine_id or "-",
            )

    async def stop(self) -> None:
        if self._engine is None:
            return
        try:
            self._engine.transport_dispatcher.close_dispatcher()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.debug("SNMP trap receiver close ignored: {}", exc)
        self._engine = None

    def _on_pysnmp_trap(
        self,
        snmp_engine: object,
        state_reference: object,
        context_engine_id: object,
        context_name: object,
        var_binds: list,
        cb_ctx: object,
    ) -> None:
        """pysnmp callback — bridge into our async handler list."""
        try:
            transport = snmp_engine.msg_and_pdu_dsp.get_transport_info(state_reference)  # type: ignore[attr-defined]
            host, port = (transport[1] if transport else ("?", 0))
        except Exception as exc:  # noqa: BLE001 -- pysnmp internals shift; fall back gracefully
            logger.debug("trap transport lookup failed: {}", exc)
            host, port = ("?", 0)

        vb_map: dict[str, str] = {}
        trap_oid: str | None = None
        for oid, value in var_binds:
            oid_s = str(oid)
            val_s = str(value)
            vb_map[oid_s] = val_s
            if oid_s == "1.3.6.1.6.3.1.1.4.1.0":
                trap_oid = val_s

        evt = TrapEvent(
            source_host=str(host),
            source_port=int(port),
            community=None,
            trap_oid=trap_oid,
            varbinds=vb_map,
        )
        logger.debug(
            "Trap received from {}: oid={} varbinds={}", host, trap_oid, len(vb_map)
        )
        # Schedule each handler on the running loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for h in self._handlers:
            try:
                res = h(evt)
                if asyncio.iscoroutine(res):
                    loop.create_task(res)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Trap handler failed: {}", exc)
