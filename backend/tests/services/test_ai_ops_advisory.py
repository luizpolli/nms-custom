from datetime import datetime, timezone
import uuid

from app.api.ai_ops import _alarm_citation, _worst_alarm
from app.models.alarm import Alarm


def _alarm(severity: str, message: str = "x") -> Alarm:
    now = datetime.now(timezone.utc)
    return Alarm(
        id=uuid.uuid4(),
        source_host="r1",
        severity=severity,
        category="link",
        event_type="linkDown",
        message=message,
        correlation_key="link:r1:1",
        state="active",
        first_seen=now,
        last_seen=now,
        occurrence_count=1,
        source_type="trap",
    )


def test_worst_alarm_prefers_highest_severity():
    assert _worst_alarm([_alarm("warning"), _alarm("critical")]).severity == "critical"


def test_alarm_citation_contains_underlying_alarm_id():
    alarm = _alarm("major", "Link down")
    citation = _alarm_citation(alarm)
    assert citation.source_type == "alarm"
    assert citation.object_id == str(alarm.id)
    assert "severity=major" in citation.detail
