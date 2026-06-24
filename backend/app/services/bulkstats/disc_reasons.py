"""StarOS disc-reason code -> human-readable name lookup.

The `system` group's disc-reason-<N> bulkstats fields (and ~50+ other
schemas referencing them, see schema CSVs) carry no labels of their own —
unlike gtpu/apn/etc. counters which come with a servname/vpnname context,
a disconnect-reason counter is just a bare number keyed by its field name.
Without this lookup a per-reason chart would show "47" instead of
"Admin-disconnect". Source: StarOS Bulk Statistics and Counters Reference
(vendor doc), converted to JSON via docs/bulkstats/21-26-bulkstats-doc-spreadsheet.md.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DISC_REASON_FIELD_RE = re.compile(r"^disc-reason-(\d+)$")
_NAMES_PATH = Path(__file__).parent / "disc_reason_names.json"


@lru_cache(maxsize=1)
def _load_names() -> dict[str, str]:
    with _NAMES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def disc_reason_code(field_name: str) -> str | None:
    """Extract the numeric code from a `disc-reason-<N>` field name, or None."""
    m = _DISC_REASON_FIELD_RE.match(field_name)
    return m.group(1) if m else None


def disc_reason_name(code: str) -> str:
    """Human-readable name for a disc-reason code, falling back to the raw code."""
    return _load_names().get(code, f"reason-{code}")


def all_disc_reason_codes() -> list[str]:
    """All numeric codes covered by the bundled StarOS dictionary."""
    return list(_load_names())
