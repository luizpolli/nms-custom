"""Tests for the bulkstats schema CSV loader."""

from __future__ import annotations

import pytest

from app.services.bulkstats.schema import SchemaNotFoundError, get_schema, known_versions


def test_known_versions_includes_bundled_schemas():
    versions = known_versions()
    assert "21.25" in versions
    assert "21.26" in versions


def test_get_schema_resolves_real_gtpu_schema():
    schema = get_schema("21.25")
    fields = schema.schemas[("gtpu", "gtpuSch1")]
    assert fields[:8] == (
        "epochtime", "localdate", "localtime", "uptime",
        "vpnname", "vpnid", "servname", "servid",
    )
    assert "curr-sess" in fields


def test_get_schema_unknown_version_raises():
    with pytest.raises(SchemaNotFoundError):
        get_schema("99.99")
