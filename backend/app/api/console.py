"""Interactive SSH console — a WebSocket PTY proxy to a managed device.

Opens a real interactive SSH shell (asyncssh, `term_type="xterm"`) to the device
and proxies bytes both ways over a WebSocket so the frontend xterm.js terminal
behaves like a console session.

Protocol:
  - Auth: ``?token=<api-key>`` query param (browsers can't set WS headers). When no
    API keys are configured the socket is open (same posture as other routes).
  - Client → server: raw keystroke text written straight to the shell stdin.
  - Server → client: raw terminal output text.
  - Initial size from ``?cols=&rows=`` (defaults 120x32).
"""
from __future__ import annotations

import asyncio
import uuid

import asyncssh
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.device import Device
from app.security.auth import configured_api_keys, verify_api_key
from app.services.ssh.client import _build_connect_kwargs
from app.services.ssh.command_runner import ssh_credential_for_device

router = APIRouter()


def _authorized(token: str | None) -> bool:
    allowed = configured_api_keys()
    if not allowed:
        return True  # API auth disabled → open, consistent with the rest of the app
    return bool(token) and verify_api_key(token, allowed)


@router.websocket("/{device_id}")
async def device_console(ws: WebSocket, device_id: uuid.UUID) -> None:
    await ws.accept()

    if not _authorized(ws.query_params.get("token")):
        await ws.send_text("\r\n[auth] invalid or missing token\r\n")
        await ws.close(code=4401)
        return

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Device).options(selectinload(Device.credential)).where(Device.id == device_id)
            )
            device = result.scalar_one_or_none()
            if device is None:
                await ws.send_text("\r\n[error] device not found\r\n")
                await ws.close(code=4404)
                return
            ssh_cred = ssh_credential_for_device(device)
    except Exception as exc:  # noqa: BLE001 — surface resolution errors to the terminal
        await ws.send_text(f"\r\n[error] {exc}\r\n")
        await ws.close(code=4500)
        return

    try:
        cols = max(20, int(ws.query_params.get("cols") or 120))
        rows = max(5, int(ws.query_params.get("rows") or 32))
    except ValueError:
        cols, rows = 120, 32

    await ws.send_text(
        f"\r\n[connecting] {ssh_cred.username}@{ssh_cred.host}:{ssh_cred.port} ...\r\n"
    )
    try:
        async with asyncssh.connect(**_build_connect_kwargs(ssh_cred)) as conn:
            async with conn.create_process(term_type="xterm", term_size=(cols, rows)) as proc:
                await ws.send_text("[connected]\r\n")

                async def ssh_to_ws() -> None:
                    while True:
                        data = await proc.stdout.read(4096)
                        if not data:  # remote closed
                            break
                        await ws.send_text(data)

                async def ws_to_ssh() -> None:
                    while True:
                        proc.stdin.write(await ws.receive_text())

                _, pending = await asyncio.wait(
                    {asyncio.create_task(ssh_to_ws()), asyncio.create_task(ws_to_ssh())},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 — connect/auth/network failures
        logger.warning("console session error device={} err={}", device_id, exc)
        try:
            await ws.send_text(f"\r\n[disconnected] {exc}\r\n")
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
