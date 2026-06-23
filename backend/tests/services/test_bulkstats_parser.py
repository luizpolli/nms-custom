"""Tests for the bulkstats data file parser, against a synthetic fixture
shaped exactly like real gtpuSch1/cardSch1 rows (see schemas/bulkstatsschema_21.25.csv)
but with fake IPs/values — never real device data."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.bulkstats.parser import (
    BulkstatsParseError,
    parse_data_line,
    parse_file,
    parse_header_line,
)
from app.services.bulkstats.schema import SchemaNotFoundError, get_schema

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "bulkstats" / "sample_21.25.csv"


def test_parse_header_line():
    header = parse_header_line("Version-21.25,10.0.0.1,20260101-000000,20260101-000000,CST,-0600,260101-00:00,12345,EPC")
    assert header.version == "21.25"
    assert header.ip_address == "10.0.0.1"


def test_parse_header_line_malformed_raises():
    with pytest.raises(BulkstatsParseError):
        parse_header_line("not,a,header")


def test_parse_data_line_splits_metrics_from_labels():
    schema = get_schema("21.25")
    line = "PPM,gtpu,gtpuSch1,1782000000,20260101,000000,1000,SAEGW,2,PGW-S5,1,100,200,0,0,5000,60000,4000,50000,0,0,1000,12000,900,11000,0,0,300,"
    records = parse_data_line(line, schema)
    by_field = {r.field_name: r for r in records}
    assert by_field["curr-sess"].value == 100.0
    assert by_field["curr-sess"].labels == {"vpnname": "SAEGW", "servname": "PGW-S5"}
    # epochtime/localdate/localtime never become their own metric
    assert "epochtime" not in by_field
    assert "localdate" not in by_field
    # card/vpnname/servname are non-numeric -> labels, not metrics
    assert "vpnname" not in by_field
    assert "servname" not in by_field


def test_parse_data_line_unknown_schema_raises():
    schema = get_schema("21.25")
    with pytest.raises(SchemaNotFoundError):
        parse_data_line("PPM,nonexistent-group,nonexistentSch1,1,2,3,4", schema)


def test_parse_data_line_column_count_mismatch_raises():
    schema = get_schema("21.25")
    with pytest.raises(BulkstatsParseError):
        parse_data_line("PPM,card,cardSch1,1782000000,20260101,000000,1000,CPU-2,too-short", schema)


def test_parse_file_against_fixture():
    content = _FIXTURE.read_text(encoding="utf-8")
    result = parse_file(content)

    assert result.header.version == "21.25"
    assert result.header.ip_address == "10.0.0.1"
    # 2 valid PPM lines parsed, 1 deliberately truncated line failed
    assert result.lines_parsed == 2
    assert result.lines_failed == 1
    assert len(result.errors) == 1

    groups = {r.group for r in result.records}
    assert groups == {"gtpu", "card"}

    gtpu_sess = next(r for r in result.records if r.group == "gtpu" and r.field_name == "curr-sess")
    assert gtpu_sess.value == 100.0
    assert gtpu_sess.labels == {"vpnname": "SAEGW", "servname": "PGW-S5"}


def test_parse_file_empty_raises():
    with pytest.raises(BulkstatsParseError):
        parse_file("")
