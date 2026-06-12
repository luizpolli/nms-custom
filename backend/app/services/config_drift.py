"""Config drift detection — normalize, hash, and diff device configurations.

Volatile header lines (change timestamps, byte counts, ntp clock-period)
are stripped before hashing so two captures of an unchanged config produce
the same hash and deduplicate, and so drift diffs only show real changes.
"""

from __future__ import annotations

import difflib
import hashlib
import re

# Lines that change between captures without representing a config change.
_VOLATILE_LINE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^Building configuration"),
    re.compile(r"^Current configuration\s*:"),
    re.compile(r"^!!? ?Last configuration change at"),          # IOS XE (!) / IOS XR (!!)
    re.compile(r"^! NVRAM config last updated"),
    re.compile(r"^!! Building configuration"),
    re.compile(r"^!! IOS XR Configuration"),
    re.compile(r"^ntp clock-period"),
    re.compile(r"^! No configuration change since last restart"),
)


def normalize_config(raw: str) -> str:
    """Strip volatile lines and normalize whitespace/line endings."""
    lines: list[str] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.rstrip()
        if any(pattern.match(line) for pattern in _VOLATILE_LINE_RES):
            continue
        lines.append(line)
    # Drop leading/trailing blank lines left behind by stripped headers.
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def config_hash(normalized: str) -> str:
    """SHA-256 hex digest of a normalized config."""
    return hashlib.sha256(normalized.encode()).hexdigest()


def unified_config_diff(old: str, new: str, old_label: str, new_label: str) -> str:
    """Unified diff between two (normalized) configs. Empty string = identical."""
    diff_lines = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=old_label,
        tofile=new_label,
        lineterm="",
    )
    return "\n".join(diff_lines)


def drift_summary(diff_text: str) -> dict[str, int]:
    """Count added/removed lines in a unified diff (headers excluded)."""
    added = sum(
        1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    removed = sum(
        1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---")
    )
    return {"added": added, "removed": removed}
