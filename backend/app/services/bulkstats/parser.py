"""Parses a single StarOS bulkstats data CSV into structured raw records.

File shape (one HEADER line, many PPM data lines, one FOOTER line)::

    Version-21.25,10.150.172.68,20260621-000000,20260620-180000,CST,-0600,260620-18:00,98639,EPC
    PPM,gtpu,gtpuSch1,1782000000,20260620,180000,20966653,SAEGW,2,PGW-S5,1,610098,...
    ...
    EndOfFile

Each PPM line's values are zipped positionally against the schema's field
names for that (group, schema_name). A value that parses as a number
becomes a metric (one BulkstatsRecord); everything else (card names,
service names, etc.) becomes a label attached to every metric on that
line — these are device-side identifiers, not numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .schema import BulkstatsSchema, SchemaNotFoundError, get_schema

# epochtime/localdate/localtime are folded into BulkstatsRecord.timestamp and
# dropped from the output instead of being emitted as their own metric/label.
_TIMESTAMP_FIELDS = {"epochtime", "localdate", "localtime"}


class BulkstatsParseError(ValueError):
    """Raised for a file-level parse failure (bad header, empty file, ...)."""


@dataclass(frozen=True, slots=True)
class BulkstatsHeader:
    version: str
    ip_address: str
    raw_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BulkstatsRecord:
    group: str
    schema_name: str
    field_name: str
    value: float | None
    raw_value: str
    timestamp: datetime
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ParseResult:
    header: BulkstatsHeader
    records: list[BulkstatsRecord]
    lines_parsed: int
    lines_failed: int
    errors: list[str]


def _try_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_header_line(line: str) -> BulkstatsHeader:
    parts = line.strip().split(",")
    if len(parts) < 2 or "-" not in parts[0]:
        raise BulkstatsParseError(f"Malformed bulkstats header line: {line!r}")
    version = parts[0].split("-", 1)[1]
    ip_address = parts[1]
    if not ip_address:
        raise BulkstatsParseError(f"Bulkstats header line is missing an ip address: {line!r}")
    return BulkstatsHeader(version=version, ip_address=ip_address, raw_fields=tuple(parts))


def parse_data_line(line: str, schema: BulkstatsSchema) -> list[BulkstatsRecord]:
    """Parse one ``PPM,...`` line into zero or more metric records.

    Raises SchemaNotFoundError if (group, schema_name) isn't defined for
    this schema version, or ValueError for a structurally malformed line.
    """
    cols = line.split(",")
    if len(cols) < 4 or cols[0] != "PPM":
        raise BulkstatsParseError(f"Not a PPM data line: {line!r}")

    group, schema_name = cols[1], cols[2]
    values = cols[3:]
    field_names = schema.schemas.get((group, schema_name))
    if field_names is None:
        raise SchemaNotFoundError(
            f"No schema entry for ({group!r}, {schema_name!r}) in version {schema.version}"
        )

    timestamp = datetime.now(UTC)
    if "epochtime" in field_names:
        epoch_idx = field_names.index("epochtime")
        if epoch_idx < len(values):
            epoch_value = _try_float(values[epoch_idx])
            if epoch_value is not None:
                timestamp = datetime.fromtimestamp(epoch_value, tz=UTC)

    if len(values) != len(field_names):
        raise BulkstatsParseError(
            f"({group}, {schema_name}) expects {len(field_names)} values, got {len(values)}: {line!r}"
        )

    labels: dict[str, str] = {}
    metrics: list[tuple[str, str]] = []
    for field_name, raw_value in zip(field_names, values, strict=True):
        if not field_name or field_name in _TIMESTAMP_FIELDS or not raw_value:
            continue
        if _try_float(raw_value) is None:
            labels[field_name] = raw_value
        else:
            metrics.append((field_name, raw_value))

    return [
        BulkstatsRecord(
            group=group,
            schema_name=schema_name,
            field_name=metric_field,
            value=_try_float(raw_value),
            raw_value=raw_value,
            timestamp=timestamp,
            labels=dict(labels),
        )
        for metric_field, raw_value in metrics
    ]


def parse_file(content: str) -> ParseResult:
    lines = [ln for ln in content.splitlines() if ln.strip()]
    if not lines:
        raise BulkstatsParseError("Empty bulkstats file")

    header = parse_header_line(lines[0])
    schema = get_schema(header.version)

    records: list[BulkstatsRecord] = []
    lines_parsed = 0
    lines_failed = 0
    errors: list[str] = []

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "EndOfFile" or not stripped.startswith("PPM,"):
            continue
        try:
            records.extend(parse_data_line(stripped, schema))
        except (BulkstatsParseError, SchemaNotFoundError) as exc:
            lines_failed += 1
            errors.append(str(exc))
            continue
        lines_parsed += 1

    return ParseResult(
        header=header,
        records=records,
        lines_parsed=lines_parsed,
        lines_failed=lines_failed,
        errors=errors,
    )
