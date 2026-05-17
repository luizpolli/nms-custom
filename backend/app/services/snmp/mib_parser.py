"""Lightweight SMIv2 MIB parser for module and notification metadata.

This intentionally extracts only safe metadata needed by the UI/rule builder:
module identity plus NOTIFICATION-TYPE names, OBJECTS varbinds, DESCRIPTION,
and symbolic OID assignment. Full ASN.1 compilation/resolution stays in pysnmp.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MIBNotification:
    name: str
    oid: str | None = None
    objects: list[str] = field(default_factory=list)
    description: str | None = None


@dataclass(frozen=True)
class MIBSummary:
    module_name: str | None = None
    module_identity_oid: str | None = None
    notifications: list[MIBNotification] = field(default_factory=list)


def _strip_comments(text: str) -> str:
    return re.sub(r"--.*?$", "", text, flags=re.MULTILINE)


def _clean_description(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value.replace('"\n"', " ")).strip()


def _clean_oid(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip()


def parse_mib_text(text: str) -> MIBSummary:
    """Extract a compact MIB summary from SMIv2-ish text."""
    body = _strip_comments(text)

    module_match = re.search(r"\b([A-Za-z][\w-]*)\s+DEFINITIONS\s+::=\s+BEGIN\b", body)
    module_name = module_match.group(1) if module_match else None

    module_oid = None
    module_identity_match = re.search(
        r"\b[A-Za-z][\w-]*\s+MODULE-IDENTITY\b.*?::=\s*\{\s*([^}]+?)\s*\}",
        body,
        flags=re.DOTALL,
    )
    if module_identity_match:
        module_oid = _clean_oid(module_identity_match.group(1))

    notifications: list[MIBNotification] = []
    for match in re.finditer(
        r"\b(?P<name>[A-Za-z][\w-]*)\s+NOTIFICATION-TYPE\b(?P<body>.*?)::=\s*\{\s*(?P<oid>[^}]+?)\s*\}",
        body,
        flags=re.DOTALL,
    ):
        block = match.group("body")
        objects: list[str] = []
        objects_match = re.search(r"\bOBJECTS\s*\{(?P<objects>.*?)\}", block, flags=re.DOTALL)
        if objects_match:
            objects = [obj.strip() for obj in objects_match.group("objects").replace("\n", " ").split(",") if obj.strip()]

        desc_match = re.search(r'\bDESCRIPTION\s+"(?P<description>(?:[^"\\]|\\.)*)"', block, flags=re.DOTALL)
        notifications.append(
            MIBNotification(
                name=match.group("name"),
                oid=_clean_oid(match.group("oid")),
                objects=objects,
                description=_clean_description(desc_match.group("description") if desc_match else None),
            )
        )

    return MIBSummary(module_name=module_name, module_identity_oid=module_oid, notifications=notifications)
