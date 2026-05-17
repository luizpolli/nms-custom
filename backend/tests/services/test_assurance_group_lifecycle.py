import uuid
from datetime import datetime, timezone

import pytest

from app.api.assurance import GroupLifecycleRequest, suppress_group, unsuppress_group
from app.models.alarm import Alarm
from app.models.audit import AuditLog


class FakeResult:
    def __init__(self, alarms):
        self._alarms = alarms

    def scalars(self):
        return self

    def all(self):
        return self._alarms


class FakeDb:
    def __init__(self, alarms):
        self.alarms = alarms
        self.added = []

    async def execute(self, *args, **kwargs):
        return FakeResult(self.alarms)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


def _alarm(group_key='corr:r1'):
    now = datetime.now(timezone.utc)
    return Alarm(
        id=uuid.uuid4(),
        source_host='r1',
        severity='major',
        category='link',
        event_type='linkDown',
        message='Link down',
        correlation_key=group_key,
        state='active',
        first_seen=now,
        last_seen=now,
        occurrence_count=1,
        raw_varbinds={},
    )


@pytest.mark.asyncio
async def test_suppress_group_updates_matching_alarms_and_audit():
    alarms = [_alarm(), _alarm(), _alarm('other')]
    db = FakeDb(alarms)
    result = await suppress_group('corr:r1', GroupLifecycleRequest(by_user='noc', reason='maintenance'), db)  # type: ignore[arg-type]
    assert result.affected_alarm_count == 2
    assert [a.state for a in alarms] == ['suppressed', 'suppressed', 'active']
    assert alarms[0].raw_varbinds['_group_suppression']['reason'] == 'maintenance'
    assert any(isinstance(entry, AuditLog) and entry.action == 'assurance.group.suppress' for entry in db.added)


@pytest.mark.asyncio
async def test_unsuppress_group_restores_matching_alarms_and_audit():
    alarms = [_alarm(), _alarm(), _alarm('other')]
    for alarm in alarms[:2]:
        alarm.state = 'suppressed'
        alarm.raw_varbinds = {'_group_suppression': {'reason': 'maintenance'}}
    db = FakeDb(alarms)
    result = await unsuppress_group('corr:r1', GroupLifecycleRequest(by_user='noc'), db)  # type: ignore[arg-type]
    assert result.state == 'active'
    assert [a.state for a in alarms] == ['active', 'active', 'active']
    assert alarms[0].raw_varbinds is None
    assert any(isinstance(entry, AuditLog) and entry.action == 'assurance.group.unsuppress' for entry in db.added)
