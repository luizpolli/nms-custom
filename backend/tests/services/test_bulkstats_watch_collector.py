"""Tests for the bulkstats watch-path collector's file-move orchestration.

Uses a small fake session (no real DB — see test_bulkstats_ingest.py for why)
and a real tmp_path directory to exercise the actual filesystem moves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.bulkstats.watch_collector import (
    FAILED_DIRNAME,
    PROCESSED_DIRNAME,
    run_watch_pass,
)

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "bulkstats" / "sample_21.25.csv"


class _FakeResult:
    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return self

    def all(self):
        return []


class _FakeSession:
    async def execute(self, stmt):
        return _FakeResult()

    def add(self, obj):
        pass

    def add_all(self, objs):
        pass

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _fake_session_factory():
    return _FakeSession()


@pytest.mark.asyncio
async def test_run_watch_pass_ingests_and_moves_valid_file(tmp_path):
    watch_dir = tmp_path / "incoming"
    watch_dir.mkdir()
    (watch_dir / "good_bulkstats_1.csv").write_text(_FIXTURE.read_text())

    result = await run_watch_pass(_fake_session_factory, str(watch_dir))

    assert result.files_ingested == 1
    assert result.files_failed == 0
    assert not (watch_dir / "good_bulkstats_1.csv").exists()
    assert (watch_dir / PROCESSED_DIRNAME / "good_bulkstats_1.csv").exists()


@pytest.mark.asyncio
async def test_run_watch_pass_moves_unparseable_file_to_failed(tmp_path):
    watch_dir = tmp_path / "incoming"
    watch_dir.mkdir()
    (watch_dir / "garbage.csv").write_text("not,a,valid,bulkstats,header\n")

    result = await run_watch_pass(_fake_session_factory, str(watch_dir))

    assert result.files_ingested == 0
    assert result.files_failed == 1
    assert not (watch_dir / "garbage.csv").exists()
    assert (watch_dir / FAILED_DIRNAME / "garbage.csv").exists()


@pytest.mark.asyncio
async def test_run_watch_pass_skips_already_processed_files(tmp_path):
    watch_dir = tmp_path / "incoming"
    watch_dir.mkdir()
    (watch_dir / "first.csv").write_text(_FIXTURE.read_text())

    first = await run_watch_pass(_fake_session_factory, str(watch_dir))
    assert first.files_ingested == 1

    # Second pass over the same directory: nothing left directly inside it,
    # processed/ must not be re-scanned.
    second = await run_watch_pass(_fake_session_factory, str(watch_dir))
    assert second.files_ingested == 0
    assert second.files_failed == 0


@pytest.mark.asyncio
async def test_run_watch_pass_missing_directory_is_a_noop():
    result = await run_watch_pass(_fake_session_factory, "/nonexistent/path/for/sure")
    assert result.files_ingested == 0
    assert result.files_failed == 0
