"""High-level SNMP engine facade — what callers use.

Combines :class:`SNMPPoller`, :class:`MIBLoader`, the OID registry and the
:class:`SNMPTrapReceiver` into one entry point so the rest of the system
(KPI engine, discovery, topology) only depends on this module.

    engine = SNMPEngine()
    cred = SNMPCredential(version="v2c", community="public")
    sys = await engine.get_system_info("10.0.0.1", cred)
    ifs = await engine.get_interfaces("10.0.0.1", cred)
    cpu_mem = await engine.get_cpu_memory("10.0.0.1", cred)
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from app.services.snmp.mib_loader import MIBLoader
from app.services.snmp.oid_registry import OID_REGISTRY, oid_name, resolve_oid
from app.services.snmp.poller import SNMPCredential, SNMPPoller, SNMPResult
from app.services.snmp.trap_receiver import SNMPTrapReceiver, TrapEvent


@dataclass(slots=True)
class InterfaceRow:
    """One row of the IF-MIB ifTable, indexed by ifIndex."""

    if_index: int
    descr: str | None = None
    type_: int | None = None
    speed: int | None = None
    admin_status: int | None = None
    oper_status: int | None = None
    in_octets: int | None = None
    out_octets: int | None = None
    in_errors: int | None = None
    out_errors: int | None = None
    alias: str | None = None
    phys_address: str | None = None


@dataclass(slots=True)
class PhysicalInventoryRow:
    """One ENTITY-MIB entPhysicalTable row, indexed by entPhysicalIndex."""

    physical_index: int
    description: str | None = None
    vendor_type: str | None = None
    contained_in: int | None = None
    physical_class: int | None = None
    parent_rel_pos: int | None = None
    name: str | None = None
    hardware_rev: str | None = None
    firmware_rev: str | None = None
    software_rev: str | None = None
    serial_number: str | None = None
    manufacturer: str | None = None
    model_name: str | None = None
    alias: str | None = None
    asset_id: str | None = None
    is_fru: bool | None = None

    def to_chassis_inventory(self) -> dict[str, object]:
        """Return the JSON shape persisted for chassis-view enrichment."""
        return {
            "physicalIndex": self.physical_index,
            "description": self.description,
            "vendorType": self.vendor_type,
            "containedPhysicalIndex": self.contained_in,
            "physicalClass": self.physical_class,
            "parentRelPos": self.parent_rel_pos,
            "name": self.name,
            "hardwareVersion": self.hardware_rev,
            "firmwareVersion": self.firmware_rev,
            "softwareVersion": self.software_rev,
            "serialNumber": self.serial_number,
            "manufacturer": self.manufacturer,
            "modelName": self.model_name,
            "alias": self.alias,
            "assetId": self.asset_id,
            "isFRUable": self.is_fru,
        }


class SNMPEngine:
    """Facade over poller + MIB loader + trap receiver."""

    def __init__(
        self,
        mib_loader: MIBLoader | None = None,
        trap_receiver: SNMPTrapReceiver | None = None,
    ) -> None:
        self.poller = SNMPPoller()
        self.mibs = mib_loader or MIBLoader.from_env()
        self.mibs.attach_to_engine(self.poller._engine)  # noqa: SLF001
        self.trap_receiver = trap_receiver

    # ----- core ops -----

    async def get(
        self, host: str, names_or_oids: list[str], cred: SNMPCredential
    ) -> SNMPResult:
        oids = [resolve_oid(n) for n in names_or_oids]
        return await self.poller.get(host, oids, cred)

    async def walk(
        self, host: str, name_or_oid: str, cred: SNMPCredential
    ) -> SNMPResult:
        return await self.poller.bulk_walk(host, resolve_oid(name_or_oid), cred)

    # ----- high-level helpers -----

    async def get_system_info(self, host: str, cred: SNMPCredential) -> dict[str, str]:
        """Return the SNMPv2-MIB system group as a {name: value} dict."""
        names = ["sysDescr", "sysObjectID", "sysUpTime", "sysContact", "sysName", "sysLocation"]
        result = await self.get(host, names, cred)
        if not result.success:
            logger.warning("system info failed for {}: {}", host, result.error)
            return {}
        out: dict[str, str] = {}
        for oid, val in result.varbinds.items():
            n = oid_name(oid)
            if n:
                out[n] = val
        return out

    async def get_interfaces(
        self, host: str, cred: SNMPCredential
    ) -> dict[int, InterfaceRow]:
        """Walk ifTable + ifXTable and return rows keyed by ifIndex."""
        rows: dict[int, InterfaceRow] = {}

        # Columns we care about — walk each separately so a single failure doesn't
        # poison the whole inventory.
        column_map = {
            "ifDescr": "descr",
            "ifType": "type_",
            "ifSpeed": "speed",
            "ifAdminStatus": "admin_status",
            "ifOperStatus": "oper_status",
            "ifInOctets": "in_octets",
            "ifOutOctets": "out_octets",
            "ifInErrors": "in_errors",
            "ifOutErrors": "out_errors",
            "ifAlias": "alias",
            "ifPhysAddress": "phys_address",
        }

        for col_name, attr in column_map.items():
            base = OID_REGISTRY[col_name]
            res = await self.poller.bulk_walk(host, base, cred)
            if not res.success:
                continue
            for oid, val in res.varbinds.items():
                # ifIndex is the suffix after the column OID
                if not oid.startswith(base + "."):
                    continue
                idx_str = oid[len(base) + 1:]
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue
                row = rows.setdefault(idx, InterfaceRow(if_index=idx))
                # Best-effort numeric conversion for counters
                if attr in ("type_", "speed", "admin_status", "oper_status",
                            "in_octets", "out_octets", "in_errors", "out_errors"):
                    try:
                        setattr(row, attr, int(val))
                    except (ValueError, TypeError):
                        setattr(row, attr, None)
                else:
                    setattr(row, attr, val)
        return rows

    async def get_physical_inventory(
        self, host: str, cred: SNMPCredential
    ) -> dict[int, PhysicalInventoryRow]:
        """Walk ENTITY-MIB entPhysicalTable and return rows keyed by physical index."""
        rows: dict[int, PhysicalInventoryRow] = {}
        column_map = {
            "entPhysicalDescr": "description",
            "entPhysicalVendorType": "vendor_type",
            "entPhysicalContainedIn": "contained_in",
            "entPhysicalClass": "physical_class",
            "entPhysicalParentRelPos": "parent_rel_pos",
            "entPhysicalName": "name",
            "entPhysicalHardwareRev": "hardware_rev",
            "entPhysicalFirmwareRev": "firmware_rev",
            "entPhysicalSoftwareRev": "software_rev",
            "entPhysicalSerialNum": "serial_number",
            "entPhysicalMfgName": "manufacturer",
            "entPhysicalModelName": "model_name",
            "entPhysicalAlias": "alias",
            "entPhysicalAssetID": "asset_id",
            "entPhysicalIsFRU": "is_fru",
        }

        for col_name, attr in column_map.items():
            base = OID_REGISTRY[col_name]
            res = await self.poller.bulk_walk(host, base, cred)
            if not res.success:
                continue
            for oid, val in res.varbinds.items():
                if not oid.startswith(base + "."):
                    continue
                idx_str = oid[len(base) + 1:]
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue
                row = rows.setdefault(idx, PhysicalInventoryRow(physical_index=idx))
                if attr in {"contained_in", "physical_class", "parent_rel_pos"}:
                    try:
                        setattr(row, attr, int(val))
                    except (ValueError, TypeError):
                        setattr(row, attr, None)
                elif attr == "is_fru":
                    setattr(row, attr, str(val).strip().lower() in {"1", "true", "yes"})
                else:
                    setattr(row, attr, val.strip() if isinstance(val, str) else val)
        return rows

    async def get_cpu_memory(
        self, host: str, cred: SNMPCredential
    ) -> dict[str, float | None]:
        """Best-effort CPU% (1m/5m/15m) and memory used/free, Cisco-flavored."""
        out: dict[str, float | None] = {
            "cpu_1min": None, "cpu_5min": None, "cpu_15min": None,
            "mem_used": None, "mem_free": None, "mem_used_pct": None,
        }
        # CPU
        cpu = await self.poller.bulk_walk(host, OID_REGISTRY["cpmCPUTotal5minRev"], cred)
        if cpu.success and cpu.varbinds:
            try:
                out["cpu_5min"] = float(next(iter(cpu.varbinds.values())))
            except (ValueError, StopIteration):
                pass
        cpu1 = await self.poller.bulk_walk(host, OID_REGISTRY["cpmCPUTotal1minRev"], cred)
        if cpu1.success and cpu1.varbinds:
            try:
                out["cpu_1min"] = float(next(iter(cpu1.varbinds.values())))
            except (ValueError, StopIteration):
                pass

        # Memory (sum across all pools)
        used_walk = await self.poller.bulk_walk(host, OID_REGISTRY["ciscoMemoryPoolUsed"], cred)
        free_walk = await self.poller.bulk_walk(host, OID_REGISTRY["ciscoMemoryPoolFree"], cred)
        if used_walk.success and free_walk.success:
            try:
                used = sum(int(v) for v in used_walk.varbinds.values())
                free = sum(int(v) for v in free_walk.varbinds.values())
                total = used + free
                out["mem_used"] = float(used)
                out["mem_free"] = float(free)
                if total > 0:
                    out["mem_used_pct"] = used / total * 100.0
            except (ValueError, TypeError):
                pass
        return out

    async def discover_lldp_neighbors(
        self, host: str, cred: SNMPCredential
    ) -> list[dict[str, str]]:
        """Walk lldpRemTable; returns list of {sys_name, port_id, port_desc, chassis_id}."""
        neighbors: dict[str, dict[str, str]] = {}
        for col, attr in [
            ("lldpRemSysName", "sys_name"),
            ("lldpRemPortId", "port_id"),
            ("lldpRemPortDesc", "port_desc"),
            ("lldpRemChassisId", "chassis_id"),
        ]:
            base = OID_REGISTRY[col]
            res = await self.poller.bulk_walk(host, base, cred)
            if not res.success:
                continue
            for oid, val in res.varbinds.items():
                if not oid.startswith(base + "."):
                    continue
                key = oid[len(base) + 1:]
                neighbors.setdefault(key, {})[attr] = val
        return list(neighbors.values())

    async def discover_cdp_neighbors(
        self, host: str, cred: SNMPCredential
    ) -> list[dict[str, str]]:
        """Walk cdpCacheTable; returns Cisco neighbor records."""
        neighbors: dict[str, dict[str, str]] = {}
        for col, attr in [
            ("cdpCacheDeviceId", "device_id"),
            ("cdpCacheDevicePort", "device_port"),
            ("cdpCachePlatform", "platform"),
            ("cdpCacheAddress", "address"),
        ]:
            base = OID_REGISTRY[col]
            res = await self.poller.bulk_walk(host, base, cred)
            if not res.success:
                continue
            for oid, val in res.varbinds.items():
                if not oid.startswith(base + "."):
                    continue
                key = oid[len(base) + 1:]
                neighbors.setdefault(key, {})[attr] = val
        return list(neighbors.values())

    # ----- traps -----

    def attach_trap_receiver(self, receiver: SNMPTrapReceiver) -> None:
        self.trap_receiver = receiver

    def close(self) -> None:
        self.poller.close()


__all__ = ["SNMPEngine", "SNMPCredential", "SNMPResult", "InterfaceRow", "PhysicalInventoryRow", "TrapEvent"]
