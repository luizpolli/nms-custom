"""Loader for StarOS bulkstats schema definition files.

Each ``bulkstatsschema_<version>.csv`` declares, per (group, schema_name),
the ordered list of field names that line up positionally with the values
in a matching ``PPM,<group>,<schema_name>,...`` line of an actual bulkstats
data file. Schema rows always look like:

    PPM,gtpu,gtpuSch1,%epochtime%,%localdate%,%localtime%,%uptime%,%card%,...

Selecting the right file happens at parse time, driven by the
``Version-X.Y`` token every data file's own first (HEADER) line declares —
StarOS schema layouts drift between releases, so there is no single fixed
schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

_SCHEMA_DIR = Path(__file__).parent / "schemas"


class SchemaNotFoundError(LookupError):
    """Raised when no schema file is registered for a declared version, or
    when a (group, schema_name) pair isn't defined within a known version."""


@dataclass(frozen=True, slots=True)
class BulkstatsSchema:
    version: str
    header_fields: tuple[str, ...]
    schemas: dict[tuple[str, str], tuple[str, ...]]


def _strip_token(token: str) -> str:
    return token.strip().strip("%")


def _parse_schema_file(path: Path) -> BulkstatsSchema:
    version: str | None = None
    header_fields: tuple[str, ...] = ()
    schemas: dict[tuple[str, str], tuple[str, ...]] = {}

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("HEADER:"):
            parts = line[len("HEADER:"):].split(",")
            version = parts[0].split("-", 1)[1] if "-" in parts[0] else parts[0]
            header_fields = tuple(_strip_token(p) for p in parts[1:])
            continue
        if line.startswith("FOOTER:"):
            continue
        if line.startswith("PPM,"):
            cols = line.split(",")
            if len(cols) < 3:
                continue
            group, schema_name = cols[1], cols[2]
            field_names = tuple(_strip_token(c) for c in cols[3:])
            schemas[(group, schema_name)] = field_names

    if version is None:
        raise ValueError(f"No HEADER line found in bulkstats schema file {path}")
    return BulkstatsSchema(version=version, header_fields=header_fields, schemas=schemas)


@cache
def _load_all_schemas() -> dict[str, BulkstatsSchema]:
    registry: dict[str, BulkstatsSchema] = {}
    for path in sorted(_SCHEMA_DIR.glob("bulkstatsschema_*.csv")):
        parsed = _parse_schema_file(path)
        registry[parsed.version] = parsed
    return registry


def get_schema(version: str) -> BulkstatsSchema:
    schema = _load_all_schemas().get(version)
    if schema is None:
        raise SchemaNotFoundError(
            f"No bulkstats schema registered for version {version!r}. "
            f"Known versions: {sorted(_load_all_schemas())}"
        )
    return schema


def known_versions() -> tuple[str, ...]:
    return tuple(sorted(_load_all_schemas()))
