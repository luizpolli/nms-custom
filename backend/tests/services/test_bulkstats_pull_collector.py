"""Tests for the active-pull (SSH/SFTP) bulkstats collector.

Both the SSH transport (source_factory) and credential decryption
(credential_resolver) are injectable on run_pull_pass specifically so these
tests never touch a real SSH connection or the credential vault — only the
collector's own orchestration logic (device targeting, dedup, error
isolation) is under test here.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.models.bulkstats import BulkstatsCounterCatalog, BulkstatsIngestionStat
from app.models.device import Device
from app.services.bulkstats.pull_collector import run_pull_pass

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "bulkstats" / "sample_21.25.csv"


def _find_eq_filter_value(stmt, column_name: str):
    """Extract the literal bound to `column_name == ...` in stmt's WHERE,
    walking through an AND-conjunction if present. Returns None if absent."""
    clause = stmt.whereclause
    if clause is None:
        return None
    conditions = list(clause.clauses) if hasattr(clause, "clauses") else [clause]
    for cond in conditions:
        left_name = getattr(cond.left, "name", None) or getattr(cond.left, "key", None)
        if left_name == column_name:
            return cond.right.value
    return None


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else []


class FakeSession:
    """Routes select() by target entity + a recognized equality filter.

    Both ingest_file() (single-device-by-ip_address lookups) and
    pull_collector's own device-targeting query (device_type+ssh_enabled,
    no ip_address filter) hit Device — this distinguishes them by whether
    an ip_address filter is present rather than by entity class alone.
    """

    def __init__(self, *, devices: list[Device], stats: dict[str, BulkstatsIngestionStat] | None = None):
        self.devices = devices
        self.stats = stats if stats is not None else {}
        self.added: list = []

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Device:
            ip_filter = _find_eq_filter_value(stmt, "ip_address")
            if ip_filter is not None:
                return _FakeResult(next((d for d in self.devices if d.ip_address == ip_filter), None))
            return _FakeResult(list(self.devices))
        if entity is BulkstatsCounterCatalog:
            return _FakeResult([])
        if entity is BulkstatsIngestionStat:
            target_ip = _find_eq_filter_value(stmt, "source_ip")
            return _FakeResult(self.stats.get(target_ip))
        raise AssertionError(f"Unexpected query target: {entity}")

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, BulkstatsIngestionStat):
            self.stats[obj.source_ip] = obj

    def add_all(self, objs):
        for obj in objs:
            self.add(obj)

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _device(ip: str) -> Device:
    return Device(id=uuid.uuid4(), name=f"spgw-{ip}", ip_address=ip, device_type="staros", ssh_enabled=True)


class _FakeSource:
    """Canned RemoteBulkstatsSource — no real SSH/SFTP involved."""

    def __init__(self, files: dict[str, str]):
        self._files = files

    async def listdir(self, remote_path: str) -> list[str]:
        return list(self._files.keys())

    async def read_text(self, remote_path: str) -> str:
        filename = remote_path.rsplit("/", 1)[-1]
        return self._files[filename]


def _make_session_factory(session: FakeSession):
    def factory():
        return session
    return factory


@pytest.mark.asyncio
async def test_run_pull_pass_ingests_new_files_from_each_device():
    device = _device("10.0.0.1")
    session = FakeSession(devices=[device])
    sample = _FIXTURE.read_text()

    result = await run_pull_pass(
        _make_session_factory(session),
        device_type="staros",
        remote_path="/flash/bulkstats",
        source_factory=lambda _cred: _FakeSource({"file_a.csv": sample}),
        credential_resolver=lambda _device: object(),
    )

    assert result.devices_polled == 1
    assert result.devices_failed == 0
    assert result.files_ingested == 1
    assert result.files_failed == 0

    stat = session.stats["10.0.0.1"]
    assert stat.pulled_filenames == ["file_a.csv"]


@pytest.mark.asyncio
async def test_run_pull_pass_skips_already_pulled_filenames():
    device = _device("10.0.0.2")
    existing_stat = BulkstatsIngestionStat(
        source_ip="10.0.0.2", files_processed=1, lines_parsed=2, lines_failed=0,
        pulled_filenames=["file_a.csv"],
    )
    session = FakeSession(devices=[device], stats={"10.0.0.2": existing_stat})
    sample = _FIXTURE.read_text()

    result = await run_pull_pass(
        _make_session_factory(session),
        device_type="staros",
        remote_path="/flash/bulkstats",
        source_factory=lambda _cred: _FakeSource({"file_a.csv": sample, "file_b.csv": sample}),
        credential_resolver=lambda _device: object(),
    )

    # file_a.csv was already pulled before -> only file_b.csv gets ingested.
    assert result.files_ingested == 1
    assert set(existing_stat.pulled_filenames) == {"file_a.csv", "file_b.csv"}


@pytest.mark.asyncio
async def test_run_pull_pass_isolates_one_bad_device_from_the_rest():
    good_device = _device("10.0.0.3")
    bad_device = _device("10.0.0.4")
    session = FakeSession(devices=[bad_device, good_device])
    sample = _FIXTURE.read_text()

    def credential_resolver(device):
        if device.ip_address == "10.0.0.4":
            raise ValueError("Device has no credential attached")
        return object()

    result = await run_pull_pass(
        _make_session_factory(session),
        device_type="staros",
        remote_path="/flash/bulkstats",
        source_factory=lambda _cred: _FakeSource({"file_a.csv": sample}),
        credential_resolver=credential_resolver,
    )

    assert result.devices_polled == 1
    assert result.devices_failed == 1
    assert result.files_ingested == 1


@pytest.mark.asyncio
async def test_run_pull_pass_no_matching_devices_is_a_noop():
    session = FakeSession(devices=[])

    result = await run_pull_pass(
        _make_session_factory(session),
        device_type="staros",
        remote_path="/flash/bulkstats",
        source_factory=lambda _cred: _FakeSource({}),
        credential_resolver=lambda _device: object(),
    )

    assert result.devices_polled == 0
    assert result.devices_failed == 0
    assert result.files_ingested == 0
