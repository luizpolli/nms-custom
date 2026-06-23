"""Active-pull collector: connects to each StarOS device over its existing
SSH credential (Credential/SSHClient — same as config backup/CLI polling)
and fetches new bulkstats files via SFTP from
BulkstatsAdminSettings.pull.remote_path.

Read-only on the remote side by design — files are never deleted or moved on
the device, since that's a live production network element. Dedup against
re-pulling the same filename on the next poll is tracked locally via
BulkstatsIngestionStat.pulled_filenames (a bounded rolling window, keyed by
the device's source IP — the same key ingest_file() already uses).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.bulkstats import BulkstatsIngestionStat
from app.models.device import Device
from app.services.ssh.client import SSHClient, SSHCredential
from app.services.ssh.command_runner import ssh_credential_for_device

from .ingest import ingest_file

_PULLED_FILENAMES_WINDOW = 200


class RemoteBulkstatsSource(Protocol):
    async def listdir(self, remote_path: str) -> list[str]: ...
    async def read_text(self, remote_path: str) -> str: ...


class SSHBulkstatsSource:
    """Production RemoteBulkstatsSource backed by a real SSH/SFTP session."""

    def __init__(self, credential: SSHCredential) -> None:
        self._credential = credential

    async def listdir(self, remote_path: str) -> list[str]:
        async with SSHClient(self._credential) as client:
            return await client.listdir(remote_path)

    async def read_text(self, remote_path: str) -> str:
        async with SSHClient(self._credential) as client:
            return await client.read_text(remote_path)


@dataclass(slots=True)
class PullPassResult:
    devices_polled: int = 0
    devices_failed: int = 0
    files_ingested: int = 0
    files_failed: int = 0


async def _load_target_devices(session: AsyncSession, device_type: str) -> list[Device]:
    stmt = select(Device).where(Device.device_type == device_type, Device.ssh_enabled.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _already_pulled(session: AsyncSession, source_ip: str) -> set[str]:
    stmt = select(BulkstatsIngestionStat).where(BulkstatsIngestionStat.source_ip == source_ip)
    stat = (await session.execute(stmt)).scalar_one_or_none()
    return set(stat.pulled_filenames or []) if stat else set()


async def _record_pulled_filename(session: AsyncSession, source_ip: str, filename: str) -> None:
    stmt = select(BulkstatsIngestionStat).where(BulkstatsIngestionStat.source_ip == source_ip)
    stat = (await session.execute(stmt)).scalar_one_or_none()
    if stat is None:
        stat = BulkstatsIngestionStat(
            source_ip=source_ip, files_processed=0, lines_parsed=0, lines_failed=0, pulled_filenames=[]
        )
        session.add(stat)
    window = [*list(stat.pulled_filenames or []), filename]
    stat.pulled_filenames = window[-_PULLED_FILENAMES_WINDOW:]
    await session.commit()


async def _pull_from_device(
    session_factory: async_sessionmaker[AsyncSession],
    source: RemoteBulkstatsSource,
    device: Device,
    remote_path: str,
) -> tuple[int, int]:
    """Returns (files_ingested, files_failed) for this one device."""
    async with session_factory() as session:
        already = await _already_pulled(session, device.ip_address)

    remote_files = await source.listdir(remote_path)
    new_files = sorted(f for f in remote_files if f not in already)

    files_ingested = files_failed = 0
    for filename in new_files:
        try:
            content = await source.read_text(f"{remote_path.rstrip('/')}/{filename}")
            async with session_factory() as session:
                result = await ingest_file(session, filename=filename, content=content)
                await session.commit()
                await _record_pulled_filename(session, device.ip_address, filename)
            logger.info(
                "bulkstats pull: ingested {} from {} ({} raw samples, {} kpis promoted, {} lines failed)",
                filename,
                device.ip_address,
                result.raw_samples_written,
                result.kpis_promoted,
                result.lines_failed,
            )
            files_ingested += 1
        except Exception as exc:
            logger.error("bulkstats pull: failed to fetch/ingest {} from {}: {}", filename, device.ip_address, exc)
            files_failed += 1

    return files_ingested, files_failed


async def run_pull_pass(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    device_type: str,
    remote_path: str,
    source_factory=SSHBulkstatsSource,
    credential_resolver=ssh_credential_for_device,
) -> PullPassResult:
    """Poll every SSH-enabled device matching device_type for new bulkstats
    files. source_factory/credential_resolver are overridable in tests to
    avoid touching a real SSH connection or credential decryption."""
    result = PullPassResult()
    async with session_factory() as session:
        devices = await _load_target_devices(session, device_type)

    for device in devices:
        try:
            credential = credential_resolver(device)
            source = source_factory(credential)
            ingested, failed = await _pull_from_device(session_factory, source, device, remote_path)
            result.files_ingested += ingested
            result.files_failed += failed
            result.devices_polled += 1
        except Exception as exc:
            logger.error("bulkstats pull: could not poll device {} ({}): {}", device.name, device.ip_address, exc)
            result.devices_failed += 1

    return result
