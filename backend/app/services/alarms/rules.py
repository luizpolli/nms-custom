"""Alarm customization rule matching and transformation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from string import Formatter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm_rule import AlarmRule


@dataclass(frozen=True)
class AlarmRuleContext:
    source_type: str
    source_host: str
    trap_oid: str | None
    event_type: str
    category: str
    message: str
    severity: str
    varbinds: dict[str, str]
    correlation_key: str

    def value_for(self, field: str) -> str:
        value = getattr(self, field, "")
        return "" if value is None else str(value)

    def template_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "source_type": self.source_type,
            "source_host": self.source_host,
            "trap_oid": self.trap_oid or "",
            "event_type": self.event_type,
            "category": self.category,
            "message": self.message,
            "severity": self.severity,
            "correlation_key": self.correlation_key,
            "varbinds": self.varbinds,
        }
        for oid, value in self.varbinds.items():
            safe_key = "varbind_" + re.sub(r"[^0-9A-Za-z_]", "_", oid).strip("_")
            data[safe_key] = value
        return data


def _matches(rule: AlarmRule, ctx: AlarmRuleContext) -> bool:
    if rule.source_type not in ("any", ctx.source_type):
        return False

    candidate = ctx.value_for(rule.match_field)
    pattern = rule.match_pattern
    if rule.match_operator == "equals":
        return candidate == pattern
    if rule.match_operator == "starts_with":
        return candidate.startswith(pattern)
    if rule.match_operator == "contains":
        return pattern in candidate
    if rule.match_operator == "regex":
        try:
            return re.search(pattern, candidate) is not None
        except re.error:
            return False
    return False


def _render_template(template: str, data: dict[str, Any]) -> str:
    """Safely render a simple str.format template, leaving unknown fields intact."""
    values = dict(data)
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name and field_name not in values:
            values[field_name] = "{" + field_name + "}"
    try:
        return template.format_map(values)
    except Exception:
        return template


async def find_matching_rule(session: AsyncSession, ctx: AlarmRuleContext) -> AlarmRule | None:
    result = await session.execute(
        select(AlarmRule)
        .where(AlarmRule.enabled.is_(True))
        .order_by(AlarmRule.priority.asc(), AlarmRule.created_at.asc())
    )
    for rule in result.scalars().all():
        if _matches(rule, ctx):
            return rule
    return None


def apply_rule(cls: dict[str, Any], rule: AlarmRule, ctx: AlarmRuleContext) -> dict[str, Any]:
    """Return a classification copy with customer rule overrides applied."""
    data = ctx.template_data()
    next_cls = dict(cls)
    next_cls["severity"] = "clear" if rule.auto_clear else rule.severity
    if rule.category:
        next_cls["category"] = rule.category
    if rule.event_type:
        next_cls["event_type"] = _render_template(rule.event_type, data)
    if rule.message_template:
        next_cls["message"] = _render_template(rule.message_template, data)
    if rule.correlation_key_template:
        next_cls["correlation_key"] = _render_template(rule.correlation_key_template, data)
    next_cls["matched_rule_id"] = str(rule.id)
    next_cls["matched_rule_name"] = rule.name
    next_cls["auto_clear"] = rule.auto_clear
    return next_cls
