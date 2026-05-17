import uuid
from datetime import datetime, timezone

from app.api.assurance import _build_groups, _interface_alarm_match
from app.models.alarm import Alarm
from app.models.interface import Interface


def _alarm(**kwargs):
    now = datetime.now(timezone.utc)
    defaults = dict(
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
        source_type="trap",
    )
    defaults.update(kwargs)
    return Alarm(**defaults)


def test_build_groups_uses_dedup_or_correlation_key():
    alarms = [_alarm(dedup_key="link:r1:7"), _alarm(dedup_key="link:r1:7", occurrence_count=2)]
    groups = _build_groups(alarms)
    assert len(groups) == 1
    assert groups[0].active_count == 2
    assert groups[0].occurrence_count == 3


def test_interface_alarm_match_by_object_id_and_ifindex():
    iface_id = uuid.uuid4()
    device_id = uuid.uuid4()
    iface = Interface(id=iface_id, device_id=device_id, name="Gi0/1", if_index=7)
    assert _interface_alarm_match(_alarm(object_type="interface", object_id=str(iface_id), device_id=device_id), iface)
    assert _interface_alarm_match(_alarm(correlation_key="link:r1:7", device_id=device_id), iface)
    assert not _interface_alarm_match(_alarm(correlation_key="link:r1:9", device_id=device_id), iface)
