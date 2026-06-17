"""System administration: container status, backup jobs."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/app/backups"))
BACKUP_CONFIG_FILE = Path(os.getenv("BACKUP_CONFIG_FILE", "/app/data/backup-config.json"))
BACKUP_SCRIPT = Path(os.getenv("BACKUP_SCRIPT", "/app/scripts/backup.sh"))

KNOWN_CONTAINERS: dict[str, dict] = {
    "nms-postgres":           {"label": "PostgreSQL",          "group": "Infrastructure", "critical": True},
    "nms-redis":              {"label": "Redis",               "group": "Infrastructure", "critical": True},
    "nms-app":                {"label": "API App",             "group": "Application",    "critical": True},
    "nms-frontend":           {"label": "Frontend",            "group": "Application",    "critical": True},
    "nms-worker-poller":      {"label": "Poller Worker",       "group": "Workers",        "critical": False},
    "nms-worker-topology":    {"label": "Topology Worker",     "group": "Workers",        "critical": False},
    "nms-worker-report":      {"label": "Report Worker",       "group": "Workers",        "critical": False},
    "nms-worker-alarm":       {"label": "Alarm Worker",        "group": "Workers",        "critical": False},
    "nms-worker-discovery":   {"label": "Discovery Worker",    "group": "Workers",        "critical": False},
    "nms-worker-telemetry":   {"label": "Telemetry Worker",    "group": "Workers",        "critical": False},
    "nms-trap-receiver":      {"label": "SNMP Trap Receiver",  "group": "Receivers",      "critical": False},
    "nms-syslog-receiver":    {"label": "Syslog Receiver",     "group": "Receivers",      "critical": False},
    "nms-telemetry-receiver": {"label": "Telemetry Receiver",  "group": "Receivers",      "critical": False},
}


async def _docker(*args: str) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()
    except FileNotFoundError:
        return -1, "", "docker CLI not found"


async def get_container_statuses() -> dict:
    rc, out, _ = await _docker(
        "ps", "-a",
        "--format", "{{.Names}}\t{{.Status}}\t{{.State}}",
    )
    docker_states: dict[str, dict] = {}
    if rc == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                docker_states[parts[0]] = {
                    "status_text": parts[1],
                    "state": parts[2],
                }

    containers = []
    for name, meta in KNOWN_CONTAINERS.items():
        info = docker_states.get(name, {})
        containers.append({
            "name": name,
            "label": meta["label"],
            "group": meta["group"],
            "critical": meta["critical"],
            "state": info.get("state", "unknown"),
            "status_text": info.get("status_text", "—"),
        })
    return {"docker_available": rc == 0, "containers": containers}


async def restart_container(name: str) -> dict:
    if name not in KNOWN_CONTAINERS:
        return {"ok": False, "error": "Unknown container"}
    rc, out, err = await _docker("restart", name)
    return {"ok": rc == 0, "error": err if rc != 0 else None}


def list_backups(backup_dir: Path | None = None) -> list[dict]:
    d = backup_dir or BACKUP_DIR
    if not d.exists():
        return []
    results = []
    for entry in sorted(d.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        files = [f.name for f in entry.iterdir() if f.is_file()]
        size = sum((entry / f).stat().st_size for f in files)
        results.append({
            "name": entry.name,
            "size_bytes": size,
            "files": files,
            "has_manifest": "MANIFEST.txt" in files,
        })
    return results


async def trigger_backup(
    skip_redis: bool = False,
    include_volumes: bool = False,
    backup_dir: Path | None = None,
) -> dict:
    d = backup_dir or BACKUP_DIR
    d.mkdir(parents=True, exist_ok=True)
    cmd = ["bash", str(BACKUP_SCRIPT), "--dir", str(d)]
    if skip_redis:
        cmd.append("--skip-redis")
    if include_volumes:
        cmd.append("--volumes")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return {
            "ok": proc.returncode == 0,
            "output": stdout.decode(),
            "error": stderr.decode() if proc.returncode != 0 else None,
        }
    except FileNotFoundError:
        return {"ok": False, "error": "backup.sh not found"}


def delete_backup(name: str, backup_dir: Path | None = None) -> dict:
    d = backup_dir or BACKUP_DIR
    target = d / name
    if not target.exists() or not target.is_dir():
        return {"ok": False, "error": "Backup not found"}
    if target.parent.resolve() != d.resolve():
        return {"ok": False, "error": "Invalid path"}
    shutil.rmtree(target)
    return {"ok": True}


def get_backup_config() -> dict:
    defaults: dict = {
        "enabled": False,
        "schedule": "0 2 * * *",
        "destination": "local",
        "dest_path": str(BACKUP_DIR),
        "skip_redis": False,
        "include_volumes": False,
        "retain_days": 7,
    }
    if BACKUP_CONFIG_FILE.exists():
        try:
            stored = json.loads(BACKUP_CONFIG_FILE.read_text())
            defaults.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_backup_config(config: dict) -> dict:
    BACKUP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_CONFIG_FILE.write_text(json.dumps(config, indent=2))
    return config
