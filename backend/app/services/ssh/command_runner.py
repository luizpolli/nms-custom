"""CommandRunner — executes saved or ad-hoc commands against devices via SSH."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.command import Command
from app.models.credential import Credential
from app.models.device import Device
from app.services.ssh.client import CommandResult, SSHClient, SSHCredential


class CommandRunner:
    """Runs CLI commands on devices using the SSH client.

    Requires an ``async_sessionmaker`` so it can open its own sessions
    for loading and persisting model state.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run_saved_command(self, command_id: uuid.UUID) -> CommandResult:
        """Load a saved Command, execute it, persist last_output, and return the result."""
        async with self._sf() as session:
            command = await _load_command(session, command_id)
            credential = _resolve_credential(command)
            ssh_cred = _build_ssh_credential(command.device, credential)

            logger.info(
                "run_saved_command id={} cli='{}' host={}",
                command_id,
                command.cli_command,
                command.device.ip_address,
            )
            result = await _execute(ssh_cred, command.cli_command)
            await _persist_output(session, command, result.stdout)
            return result

    async def run_ad_hoc(self, device_id: uuid.UUID, cli: str) -> CommandResult:
        """Execute a CLI string on the given device without persisting output."""
        async with self._sf() as session:
            device = await _load_device(session, device_id)
            credential = _resolve_credential_for_device(device)
            ssh_cred = _build_ssh_credential(device, credential)

        logger.info("run_ad_hoc device_id={} cli='{}' host={}", device_id, cli, device.ip_address)
        return await _execute(ssh_cred, cli)


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
    return SSHCredential(
        host=device.ip_address,
        username=credential.username,
        port=credential.port if credential.protocol == "ssh" else 22,
        password=credential.auth_key if not credential.auth_key.startswith("-----") else None,
        private_key=credential.auth_key if credential.auth_key.startswith("-----") else None,
    )


async def _execute(ssh_cred: SSHCredential, cli: str) -> CommandResult:
    async with SSHClient(ssh_cred) as client:
        return await client.run(cli)


async def _persist_output(session: AsyncSession, command: Command, output: str) -> None:
    command.last_output = output
    command.updated_at = datetime.now()
    session.add(command)
    await session.commit()
    logger.debug("Persisted last_output for command id={}", command.id)
