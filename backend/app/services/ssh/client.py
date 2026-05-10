"""Async SSH client wrapping asyncssh — command execution, SFTP, config backup.

Errors are caught at every public method boundary; callers receive a
``CommandResult`` with ``exit_status != 0`` rather than a raised exception.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

try:
    import asyncssh
    from asyncssh import SSHClientConnection, SSHCompletedProcess
except ImportError:  # pragma: no cover
    asyncssh = None  # type: ignore[assignment]
    SSHClientConnection = SSHCompletedProcess = None  # type: ignore[assignment]

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_BACKUP_COMMANDS: dict[str, str] = {
    "ios-xr": "show running-config",
    "ios-xe": "show running-config",
    "ios": "show running-config",
    "legacy": "show config",
    "nxos": "show running-config",
}


@dataclass(slots=True)
class SSHCredential:
    """SSH connection parameters for a single target host."""

    host: str
    username: str
    port: int = 22
    password: str | None = None
    private_key: str | None = None
    known_hosts_path: str | None = None
    connect_timeout: int = 10


@dataclass(slots=True)
class CommandResult:
    """Result of a single SSH command execution."""

    stdout: str
    stderr: str
    exit_status: int
    duration_ms: float
    command: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.exit_status == 0


# ---------------------------------------------------------------------------
# SSHClient
# ---------------------------------------------------------------------------


class SSHClient:
    """Async context manager providing SSH command execution and SFTP operations."""

    def __init__(self, credential: SSHCredential) -> None:
        self._cred = credential
        self._conn: SSHClientConnection | None = None

    async def __aenter__(self) -> SSHClient:
        if asyncssh is None:
            raise RuntimeError("asyncssh is not installed — pip install asyncssh")
        connect_kwargs = _build_connect_kwargs(self._cred)
        logger.debug("SSH connect → {}:{}", self._cred.host, self._cred.port)
        self._conn = await asyncssh.connect(**connect_kwargs)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    async def run(self, command: str, timeout: int = 30) -> CommandResult:
        """Execute a single command and return its result.

        Never raises — asyncssh errors are captured into CommandResult.
        """
        if self._conn is None:
            return _error_result(command, "SSHClient is not connected")
        t0 = time.monotonic()
        try:
            result: SSHCompletedProcess = await self._conn.run(
                command, timeout=timeout, check=False
            )
            duration_ms = (time.monotonic() - t0) * 1000
            logger.debug(
                "SSH run [{}] exit={} duration={:.1f}ms host={}",
                command,
                result.exit_status,
                duration_ms,
                self._cred.host,
            )
            return CommandResult(
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                exit_status=result.exit_status if result.exit_status is not None else -1,
                duration_ms=duration_ms,
                command=command,
            )
        except asyncssh.Error as exc:  # type: ignore[union-attr]
            duration_ms = (time.monotonic() - t0) * 1000
            logger.warning("SSH error on {}: {}", self._cred.host, exc)
            return _error_result(command, str(exc), duration_ms)
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.monotonic() - t0) * 1000
            logger.exception("Unexpected SSH error on {}: {}", self._cred.host, exc)
            return _error_result(command, str(exc), duration_ms)

    async def run_many(self, commands: list[str], timeout: int = 30) -> list[CommandResult]:
        """Execute commands sequentially, stopping on first non-zero exit."""
        results: list[CommandResult] = []
        for cmd in commands:
            result = await self.run(cmd, timeout=timeout)
            results.append(result)
            if not result.success:
                logger.warning(
                    "run_many stopping early — command '{}' exited {}", cmd, result.exit_status
                )
                break
        return results

    # ------------------------------------------------------------------
    # SFTP
    # ------------------------------------------------------------------

    async def download(self, remote_path: str, local_path: str) -> None:
        """Download a file from the remote host via SFTP."""
        if self._conn is None:
            raise RuntimeError("SSHClient is not connected")
        async with self._conn.start_sftp_client() as sftp:
            logger.debug("SFTP download {} → {} host={}", remote_path, local_path, self._cred.host)
            await sftp.get(remote_path, local_path)

    async def upload(self, local_path: str, remote_path: str) -> None:
        """Upload a file to the remote host via SFTP."""
        if self._conn is None:
            raise RuntimeError("SSHClient is not connected")
        async with self._conn.start_sftp_client() as sftp:
            logger.debug("SFTP upload {} → {} host={}", local_path, remote_path, self._cred.host)
            await sftp.put(local_path, remote_path)

    # ------------------------------------------------------------------
    # Config backup
    # ------------------------------------------------------------------

    async def backup_config(self, device_type: str = "ios-xr") -> str:
        """Retrieve the running configuration text from the device.

        Selects the appropriate CLI command based on ``device_type``.
        Returns the raw stdout; raises RuntimeError if the command fails.
        """
        cli = _BACKUP_COMMANDS.get(device_type.lower(), "show running-config")
        logger.info("backup_config device_type={} cmd='{}' host={}", device_type, cli, self._cred.host)
        result = await self.run(cli, timeout=60)
        if not result.success:
            raise RuntimeError(
                f"backup_config failed on {self._cred.host}: {result.stderr or result.error}"
            )
        return result.stdout


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_connect_kwargs(cred: SSHCredential) -> dict:
    """Build the kwargs dict for asyncssh.connect from an SSHCredential."""
    kwargs: dict = {
        "host": cred.host,
        "port": cred.port,
        "username": cred.username,
        "connect_timeout": cred.connect_timeout,
    }
    if cred.password is not None:
        kwargs["password"] = cred.password
    if cred.private_key is not None:
        kwargs["client_keys"] = [cred.private_key]
    if cred.known_hosts_path is not None:
        kwargs["known_hosts"] = cred.known_hosts_path
    else:
        kwargs["known_hosts"] = None  # disable host key checking when not set
    return kwargs


def _error_result(command: str, error: str, duration_ms: float = 0.0) -> CommandResult:
    return CommandResult(
        stdout="",
        stderr="",
        exit_status=1,
        duration_ms=duration_ms,
        command=command,
        error=error,
    )
