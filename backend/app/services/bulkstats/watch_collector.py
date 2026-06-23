"""Watch-path collector: polls a drop directory for bulkstats files dropped
there by an external transfer job (SCP/rsync/etc. from the StarOS device, or
any intermediary) and ingests each one.

No separate "have I seen this file" tracking table is needed: a successfully
ingested file is moved into ``<watch_path>/processed/`` so it's simply never
seen again on the next poll, and a failed one moves to ``<watch_path>/failed/``
so it doesn't vanish silently and doesn't get retried forever either.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .ingest import ingest_file

PROCESSED_DIRNAME = "processed"
FAILED_DIRNAME = "failed"


@dataclass(slots=True)
class WatchPassResult:
    files_ingested: int = 0
    files_failed: int = 0


def _list_candidate_files(watch_dir: Path) -> list[Path]:
    if not watch_dir.is_dir():
        return []
    skip = {PROCESSED_DIRNAME, FAILED_DIRNAME}
    return sorted(p for p in watch_dir.iterdir() if p.is_file() and p.name not in skip)


async def _ingest_one(session_factory: async_sessionmaker[AsyncSession], path: Path) -> None:
    content = path.read_text(encoding="utf-8", errors="replace")
    async with session_factory() as session:
        result = await ingest_file(session, filename=path.name, content=content)
        await session.commit()
    logger.info(
        "bulkstats watch: ingested {} ({} raw samples, {} kpis promoted, {} lines failed)",
        path.name,
        result.raw_samples_written,
        result.kpis_promoted,
        result.lines_failed,
    )


def _move_into(path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(exist_ok=True)
    path.rename(dest_dir / path.name)


async def run_watch_pass(session_factory: async_sessionmaker[AsyncSession], watch_path: str) -> WatchPassResult:
    """Ingest every file currently sitting directly in watch_path (one level,
    not recursive — processed/failed are subdirectories of it)."""
    watch_dir = Path(watch_path)
    result = WatchPassResult()

    for path in _list_candidate_files(watch_dir):
        try:
            await _ingest_one(session_factory, path)
            _move_into(path, watch_dir / PROCESSED_DIRNAME)
            result.files_ingested += 1
        except Exception as exc:
            logger.error("bulkstats watch: failed to ingest {}: {}", path, exc)
            try:
                _move_into(path, watch_dir / FAILED_DIRNAME)
            except OSError:
                logger.error("bulkstats watch: could not move failed file {} aside", path)
            result.files_failed += 1

    return result
