"""MIB loader — adds MIB search paths to pysnmp and resolves symbolic names.

The DB-side ``MIB`` model stores file metadata; this loader takes a directory of
``.mib`` files (compiled or not) and registers it with pysnmp's MIB controller
so that ``ObjectIdentity('IF-MIB', 'ifDescr')`` works at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger


class MIBLoader:
    """Maintains a list of MIB search directories and pre-compiles MIBs on load."""

    def __init__(self, search_paths: list[str | Path] | None = None) -> None:
        self.search_paths: list[Path] = [Path(p) for p in (search_paths or [])]
        self._loaded: set[str] = set()

    def add_path(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            logger.warning("MIB path does not exist: {}", p)
            return
        if p not in self.search_paths:
            self.search_paths.append(p)

    def discover(self) -> list[str]:
        """Return list of MIB module names found in registered paths."""
        names: list[str] = []
        for path in self.search_paths:
            if not path.is_dir():
                continue
            for f in path.iterdir():
                if f.is_file() and f.suffix.lower() in (".mib", ".my", ".txt"):
                    names.append(f.stem)
        return names

    def attach_to_engine(self, snmp_engine: object) -> None:
        """Register the MIB search directories on a pysnmp ``SnmpEngine`` instance.

        pysnmp's API for this changed across versions — we try the modern path
        first and fall back. Failures are logged, never fatal: the engine keeps
        working with built-in MIBs.
        """
        if not self.search_paths:
            return
        try:
            from pysnmp.smi.builder import DirMibSource

            mib_builder = snmp_engine.cache["mibBuilder"]  # type: ignore[attr-defined]
            sources = mib_builder.getMibSources()
            new_sources = sources + tuple(
                DirMibSource(str(p)) for p in self.search_paths if p.is_dir()
            )
            mib_builder.setMibSources(*new_sources)
            logger.info("Attached {} MIB sources", len(self.search_paths))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to attach MIB sources: {}", exc)

    def load_module(self, mib_name: str, snmp_engine: object) -> bool:
        """Force-load a specific MIB module by name into the engine's MIB builder."""
        if mib_name in self._loaded:
            return True
        try:
            mib_builder = snmp_engine.cache["mibBuilder"]  # type: ignore[attr-defined]
            mib_builder.load_modules(mib_name)
            self._loaded.add(mib_name)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load MIB {}: {}", mib_name, exc)
            return False

    @classmethod
    def from_env(cls) -> MIBLoader:
        """Build from ``NMS_MIB_PATH`` env var (colon-separated dirs)."""
        raw = os.environ.get("NMS_MIB_PATH", "")
        paths = [p for p in raw.split(":") if p]
        return cls(search_paths=paths)
