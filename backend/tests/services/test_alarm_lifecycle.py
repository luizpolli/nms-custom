import uuid
from datetime import datetime, timezone

import pytest

from app.api.alarms import AlarmSuppress, suppress_alarm, unsuppress_alarm, AlarmAck
from app.models.alarm import Alarm
from app.models.audit import AuditLog


class FakeDb:
    def __init__(self, alarm):
        self.alarm = alarm
        self.added = []

    async def execute(self, *args, **kwargs):
        return self

    def scalar_one_or_none(self):
        return self.alarm

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


def _alarm():
    now = datetime.now(timezone.utc)
    return Alarm(
        id=uuid.uuid4(),
        source_host="r1",
        severity="major",
        category="link",
        event_type="linkDown",
        message="Link down",
        correlation_key="link:r1:7",
        state="active",
        first_seen=now,
        last_seen=now,
        occurrence_count=1,
        raw_varbinds={},
    )


@pytest.mark.asyncio
async def test_suppress_alarm_sets_state_and_audit():
    alarm = _alarm()
    db = FakeDb(alarm)
    result = await suppress_alarm(alarm.id, AlarmSuppress(by_user="noc", reason="maintenance"), db)  # type: ignore[arg-type]
    assert result.state == "suppressed"
    assert alarm.raw_varbinds["_suppression"]["reason"] == "maintenance"
    assert any(isinstance(entry, AuditLog) and entry.action == "alarm.suppress" for entry in db.added)


@pytest.mark.asyncio
async def test_unsuppress_alarm_restores_active_and_audit():
    alarm = _alarm()
    alarm.state = "suppressed"
    alarm.raw_varbinds = {"_suppression": {"reason": "maintenance"}}
    db = FakeDb(alarm)
    result = await unsuppress_alarm(alarm.id, AlarmAck(by_user="noc"), db)  # type: ignore[arg-type]
    assert result.state == "active"
    assert alarm.raw_varbinds is None
    assert any(isinstance(entry, AuditLog) and entry.action == "alarm.unsuppress" for entry in db.added)
