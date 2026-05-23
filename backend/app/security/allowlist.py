"""Command allow-list enforcement.

If COMMAND_ALLOWLIST is set (comma-separated regex patterns), every CLI text
submitted at create/update/run time must fully match at least one pattern.
An empty allow-list means allow-all (safe default for development).
"""

from __future__ import annotations

import re
from functools import lru_cache

from fastapi import HTTPException, status

from app.config import settings


@lru_cache(maxsize=1)
def _compiled_patterns(raw: str) -> tuple[re.Pattern[str], ...]:
    """Parse and compile allowlist patterns. Cached for the lifetime of *raw*."""
    patterns = []
    for pat in raw.split(","):
        pat = pat.strip()
        if pat:
            patterns.append(re.compile(pat, re.IGNORECASE))
    return tuple(patterns)


def get_patterns() -> tuple[re.Pattern[str], ...]:
    raw = (settings.command_allowlist or "").strip()
    if not raw:
        return ()
    return _compiled_patterns(raw)


def assert_command_allowed(cli: str) -> None:
    """Raise HTTP 422 if *cli* does not match any configured allowlist pattern.

    No-op when COMMAND_ALLOWLIST is empty (allow-all).
    """
    patterns = get_patterns()
    if not patterns:
        return
    for pat in patterns:
        if pat.fullmatch(cli):
            return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"CLI command is not permitted by the server allow-list",
    )
