"""Export helpers for command run results."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

from loguru import logger

_ARTIFACTS_BASE = Path(os.environ.get("COMMAND_ARTIFACTS_DIR", "data/command_artifacts")).resolve()


def _safe_artifact_path(filename: str) -> Path:
    """Resolve artifact path, raising on path traversal attempts."""
    _ARTIFACTS_BASE.mkdir(parents=True, exist_ok=True)
    target = (_ARTIFACTS_BASE / filename).resolve()
    if not str(target).startswith(str(_ARTIFACTS_BASE)):
        raise ValueError(f"Path traversal rejected: {filename!r}")
    return target


def render_txt(runs: list[dict]) -> bytes:
    buf = io.StringIO()
    for r in runs:
        buf.write(f"=== Device: {r.get('device_id')} | Exit: {r.get('exit_status')} ===\n")
        buf.write(r.get("stdout") or "(no output)")
        buf.write("\n\n")
    return buf.getvalue().encode()


def render_json(runs: list[dict]) -> bytes:
    return json.dumps(runs, indent=2, default=str).encode()


def render_csv(runs: list[dict]) -> bytes:
    buf = io.StringIO()
    fields = ["device_id", "exit_status", "stdout", "stderr", "error", "started_at", "finished_at"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in runs:
        writer.writerow(r)
    return buf.getvalue().encode()


RENDERERS = {"txt": render_txt, "json": render_json, "csv": render_csv}
CONTENT_TYPES = {"txt": "text/plain", "json": "application/json", "csv": "text/csv"}


def export_to_file(filename: str, data: bytes) -> Path:
    """Write export bytes to the artifacts directory. Returns resolved path."""
    path = _safe_artifact_path(filename)
    path.write_bytes(data)
    logger.info("Command export written to {}", path)
    return path
