"""Tests for the event-driven service score snapshot trigger."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.alarm import Alarm
from app.models.interface import Interface
from app.models.service import Service, ServiceDependency, ServiceMember, ServiceScoreSnapshot
from app.services.assurance.snapshot_trigger import (
    SNAPSHOT_SEVERITIES,
    maybe_snapshot_for_alarm,
    snapshot_all_services,
)


async def _make_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Service.__table__.create)
        await conn.run_sync(ServiceMember.__table__.create)
        await conn.run_sync(ServiceDependency.__table__.create)
        await conn.run_sync(ServiceScoreSnapshot.__table__.create)
    return async_sessionmaker(engine, expire_on_commit=False)()


def _alarm(severity: str, *, device_id: uuid.UUID | None = None, state: str = "active") -> Alarm:
    now = datetime.now(timezone.utc)
    return Alarm(
        id=uuid.uuid4(),
        device_id=device_id,
        source_host="r1",
        severity=severity,
        category="link",
        event_type="linkDown",
        message="x",
        state=state,
        first_seen=now,
        last_seen=now,
        occurrence_count=1,
        raw_varbinds={},
    )


def test_severity_filter_constants_are_what_we_expect():
    assert "critical" in SNAPSHOT_SEVERITIES
    assert "major" in SNAPSHOT_SEVERITIES
    assert "clear" in SNAPSHOT_SEVERITIES
    assert "info" not in SNAPSHOT_SEVERITIES
    assert "minor" not in SNAPSHOT_SEVERITIES


async def test_low_severity_alarm_skips_snapshot():
    session = await _make_session()
    try:
        svc = Service(id=uuid.uuid4(), name="svc-a", kind="customer")
        session.add(svc)
        await session.commit()

        written = await maybe_snapshot_for_alarm(session, _alarm("info"))
        assert written == 0
        rows = (await session.execute(select(ServiceScoreSnapshot))).scalars().all()
        assert rows == []
    finally:
        await session.close()


async def test_critical_alarm_triggers_snapshot(monkeypatch):
    calls: list[str] = []

    async def fake_snapshot(_session):
        calls.append("called")
        return 3

    monkeypatch.setattr(
        "app.services.assurance.snapshot_trigger.snapshot_all_services",
        fake_snapshot,
    )

    # Use a real session shell — fake_snapshot doesn't actually query anything.
    session = await _make_session()
    try:
        n = await maybe_snapshot_for_alarm(session, _alarm("critical"))
        assert n == 3
        assert calls == ["called"]
    finally:
        await session.close()


async def test_clear_severity_triggers_snapshot(monkeypatch):
    calls: list[str] = []

    async def fake_snapshot(_session):
        calls.append("called")
        return 1

    monkeypatch.setattr(
        "app.services.assurance.snapshot_trigger.snapshot_all_services",
        fake_snapshot,
    )
    session = await _make_session()
    try:
        n = await maybe_snapshot_for_alarm(session, _alarm("clear", state="cleared"))
        assert n == 1
        assert calls == ["called"]
    finally:
        await session.close()


async def test_snapshot_helper_swallows_exceptions(monkeypatch):
    async def boom(_session):
        raise RuntimeError("db gone")

    monkeypatch.setattr(
        "app.services.assurance.snapshot_trigger.snapshot_all_services",
        boom,
    )
    session = await _make_session()
    try:
        n = await maybe_snapshot_for_alarm(session, _alarm("critical"))
        assert n == 0
    finally:
        await session.close()


async def test_snapshot_all_services_no_op_when_empty():
    session = await _make_session()
    try:
        written = await snapshot_all_services(session)
        assert written == 0
    finally:
        await session.close()
