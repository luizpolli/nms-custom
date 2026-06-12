"""CommandRunner — executes saved or ad-hoc commands against devices via SSH."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.command import Command
from app.models.command_run import CommandRun
from app.models.credential import Credential
from app.models.device import Device
from app.security.allowlist import assert_command_allowed
from app.security.crypto import CredentialVault
from app.services.ssh.client import CommandResult, SSHClient, SSHCredential

_STDOUT_MAX = 65536
_BULK_SEMAPHORE_SIZE = 8


class CommandRunner:
    """Runs CLI commands on devices using the SSH client.

    Requires an ``async_sessionmaker`` so it can open its own sessions
    for loading and persisting model state.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run_saved_command(
        self,
        command_id: uuid.UUID,
        *,
        device_id: uuid.UUID | None = None,
        triggered_by: str = "manual",
    ) -> CommandResult:
        """Load a saved Command, execute it, persist last_output and a run record."""
        async with self._sf() as session:
            command = await _load_command(session, command_id)
            target_device_id = device_id or command.device_id

            if device_id and device_id != command.device_id:
                device = await _load_device(session, device_id)
                credential = _resolve_credential_for_device(device)
                ssh_cred = _build_ssh_credential(device, credential)
            else:
                device = command.device
                credential = _resolve_credential(command)
                ssh_cred = _build_ssh_credential(device, credential)

            # Defense-in-depth: enforce allowlist at execution time too.
            assert_command_allowed(command.cli_command)

            logger.info(
                "run_saved_command id={} cli_len={} host={}",
                command_id,
                len(command.cli_command),
                device.ip_address,
            )
            started_at = datetime.now()
            result = await _execute(ssh_cred, command.cli_command)
            finished_at = datetime.now()

            command.last_output = result.stdout
            command.updated_at = datetime.now()
            session.add(command)

            run = CommandRun(
                command_id=command_id,
                device_id=target_device_id,
                started_at=started_at,
                finished_at=finished_at,
                exit_status=result.exit_status,
                stdout=(result.stdout or "")[:_STDOUT_MAX],
                stderr=(result.stderr or "")[:_STDOUT_MAX],
                triggered_by=triggered_by,
            )
            session.add(run)
            await session.commit()
            logger.debug("Persisted run id={} for command id={}", run.id, command_id)
            return result

    async def run_ad_hoc(
        self,
        device_id: uuid.UUID,
        cli: str,
        *,
        triggered_by: str = "manual",
    ) -> CommandResult:
        """Execute a CLI string on the given device without persisting output."""
        async with self._sf() as session:
            device = await _load_device(session, device_id)
            credential = _resolve_credential_for_device(device)
            ssh_cred = _build_ssh_credential(device, credential)

        # Defense-in-depth: enforce allowlist at execution time too.
        assert_command_allowed(cli)

        logger.info("run_ad_hoc device_id={} cli_len={} host={}", device_id, len(cli), device.ip_address)
        return await _execute(ssh_cred, cli)

    async def run_bulk(
        self,
        command_id: uuid.UUID,
        device_ids: list[uuid.UUID],
        *,
        triggered_by: str = "bulk",
    ) -> list[dict]:
        """Run a saved command against multiple devices concurrently.

        Returns a list of per-device result dicts with keys:
        device_id, exit_status, stdout, stderr, error.
        """
        sem = asyncio.Semaphore(_BULK_SEMAPHORE_SIZE)

        async def _run_one(dev_id: uuid.UUID) -> dict:
            async with sem:
                try:
                    result = await self.run_saved_command(
                        command_id, device_id=dev_id, triggered_by=triggered_by
                    )
                    return {
                        "device_id": str(dev_id),
                        "exit_status": result.exit_status,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "error": None,
                    }
                except Exception as exc:
                    logger.warning("bulk run failed for device {}: {}", dev_id, exc)
                    return {
                        "device_id": str(dev_id),
                        "exit_status": -1,
                        "stdout": "",
                        "stderr": "",
                        "error": str(exc),
                    }

        return list(await asyncio.gather(*[_run_one(d) for d in device_ids]))


def ssh_credential_for_device(device: Device) -> SSHCredential:
    """Resolve and decrypt the SSH credential attached to *device*.

    Raises ValueError when the device has no credential attached.
    """
    return _build_ssh_credential(device, _resolve_credential_for_device(device))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _load_command(session: AsyncSession, command_id: uuid.UUID) -> Command:
    stmt = select(Command).where(Command.id == command_id)
    row = await session.scalar(stmt)
    if row is None:
        raise ValueError(f"Command {command_id} not found")
    return row


async def _load_device(session: AsyncSession, device_id: uuid.UUID) -> Device:
    stmt = select(Device).where(Device.id == device_id)
    row = await session.scalar(stmt)
    if row is None:
        raise ValueError(f"Device {device_id} not found")
    return row


def _resolve_credential(command: Command) -> Credential:
    cred = command.device.credential
    if cred is None:
        raise ValueError(f"Device {command.device_id} has no credential attached")
    return cred


def _resolve_credential_for_device(device: Device) -> Credential:
    cred = device.credential
    if cred is None:
        raise ValueError(f"Device {device.id} has no credential attached")
    return cred


def _build_ssh_credential(device: Device, credential: Credential) -> SSHCredential:
    vault = CredentialVault.from_settings(settings)
    secret = vault.decrypt(credential.auth_key, credential.id.bytes)
    return SSHCredential(
        host=device.ip_address,
        username=credential.username,
        port=credential.port if credential.protocol == "ssh" else 22,
        password=secret if not secret.startswith("-----") else None,
        private_key=secret if secret.startswith("-----") else None,
    )


async def _execute(ssh_cred: SSHCredential, cli: str) -> CommandResult:
    async with SSHClient(ssh_cred) as client:
        return await client.run(cli)
