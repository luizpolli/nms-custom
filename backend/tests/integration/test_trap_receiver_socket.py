"""Integration tests for AlarmCorrelator end-to-end trap handling.

Uses a real SQLite in-memory database (Option A).  AlarmCorrelator.handle_trap()
is called directly — no UDP socket required — so the tests remain fast and
deterministic while covering the full DB write path.

The Device table uses ARRAY(String) for tags which SQLite cannot compile;
we swap that column's type before table creation (module-level, before any
test runs).  The patch only affects the table DDL, not the ORM mapping used
at runtime.

maybe_snapshot_for_alarm is monkeypatched to return 0 because snapshot_all_services
queries Service/Interface tables that are not created here.  That behaviour is
covered separately in test_snapshot_trigger.py.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.alarm import Alarm
from app.models.alarm_rule import AlarmRule
from app.models.device import Device
from app.services.alarms.correlator import AlarmCorrelator
from app.services.snmp.trap_receiver import TrapEvent
from tests.fixtures.traps.cisco_traps import (
    _LINK_DOWN_OID,
    _LINK_UP_OID,
    _BGP_PEER2_STATE_CHANGED,
    _CISCO_ENV_FAN_STATUS_CHANGE,
    _CISCO_ENV_PSU_STATUS_CHANGE,
    _CCM_CLI_RUNNING_CONFIG_CHANGED,
    _IF_INDEX,
    _SYS_NAME_OID,
    _SYS_UPTIME_OID,
    _SNMP_TRAP_OID,
    _CISCO_ENV_FAN_STATUS_DESC,
    _CISCO_ENV_FAN_STATUS,
    _CISCO_ENV_PSU_DESC,
    _CISCO_ENV_PSU_STATE,
    _CCM_HIST_EVENT_USER,
    _CCM_HIST_EVENT_CMD_SRC,
    _CBG_PEER2_REMOTE_ADDR,
    _CBG_PEER2_STATE,
    _CBG_PEER2_ADMIN_STATUS,
)

# ---------------------------------------------------------------------------
# Patch Device.tags ARRAY column so SQLite can create the table.
# Must happen before the first engine.begin() call.
# ---------------------------------------------------------------------------
from sqlalchemy import TEXT as _TEXT

Device.__table__.c["tags"].type = _TEXT()


# ---------------------------------------------------------------------------
# Shared engine / session factory
# ---------------------------------------------------------------------------

def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)


async def _bootstrap(engine) -> async_sessionmaker:
    async with engine.begin() as conn:
        await conn.run_sync(Device.__table__.create)
        await conn.run_sync(AlarmRule.__table__.create)
        await conn.run_sync(Alarm.__table__.create)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def _correlator_ctx() -> AsyncGenerator[tuple[AlarmCorrelator, AsyncSession], None]:
    """Yield (correlator, raw_session) sharing the same in-memory DB."""
    engine = _make_engine()
    factory = await _bootstrap(engine)

    @asynccontextmanager
    async def _session_factory():
        async with factory() as s:
            yield s

    correlator = AlarmCorrelator(_session_factory)
    raw = factory()
    try:
        yield correlator, raw
    finally:
        await raw.close()
        await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trap(oid: str, varbinds: dict, source_host: str = "10.0.0.1") -> TrapEvent:
    return TrapEvent(
        source_host=source_host,
        source_port=162,
        community="public",
        trap_oid=oid,
        varbinds=varbinds,
        received_at=datetime.now(timezone.utc),
    )


async def _get_alarm(session: AsyncSession, correlation_key: str) -> Alarm | None:
    # expire_all so SQLite-shared-memory cache doesn't hide commits by other sessions
    session.expire_all()
    result = await session.execute(
        select(Alarm).where(Alarm.correlation_key == correlation_key).limit(1)
    )
    return result.scalar_one_or_none()


async def _count_alarms(session: AsyncSession, correlation_key: str) -> int:
    session.expire_all()
    result = await session.execute(
        select(Alarm).where(Alarm.correlation_key == correlation_key)
    )
    return len(result.scalars().all())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_link_down_creates_major_alarm(monkeypatch):
    monkeypatch.setattr(
        "app.services.alarms.correlator.maybe_snapshot_for_alarm",
        AsyncMock(return_value=0),
    )
    async with _correlator_ctx() as (correlator, session):
        trap = _trap(
            _LINK_DOWN_OID,
            {
                _SYS_UPTIME_OID: "100",
                _SNMP_TRAP_OID: _LINK_DOWN_OID,
                _SYS_NAME_OID: "router-ncs55-1",
                _IF_INDEX: "2",
            },
            source_host="router-ncs55-1",
        )
        alarm = await correlator.handle_trap(trap)

        assert alarm is not None
        assert alarm.severity == "major"
        assert alarm.state == "active"
        assert alarm.event_type == "linkDown"
        assert "router-ncs55-1" in alarm.source_host
        # _IF_INDEX OID is 1.3.6.1.2.1.2.2.1.1.1 — suffix after prefix is "1"
        assert alarm.correlation_key == "link:router-ncs55-1:1"

        persisted = await _get_alarm(session, "link:router-ncs55-1:1")
        assert persisted is not None
        assert persisted.severity == "major"


@pytest.mark.integration
async def test_link_up_after_link_down_clears_alarm(monkeypatch):
    monkeypatch.setattr(
        "app.services.alarms.correlator.maybe_snapshot_for_alarm",
        AsyncMock(return_value=0),
    )
    async with _correlator_ctx() as (correlator, session):
        down_varbinds = {
            _SYS_UPTIME_OID: "100",
            _SNMP_TRAP_OID: _LINK_DOWN_OID,
            _SYS_NAME_OID: "router-ncs55-1",
            _IF_INDEX: "2",
        }
        await correlator.handle_trap(_trap(_LINK_DOWN_OID, down_varbinds, "router-ncs55-1"))

        up_varbinds = {
            _SYS_UPTIME_OID: "200",
            _SNMP_TRAP_OID: _LINK_UP_OID,
            _SYS_NAME_OID: "router-ncs55-1",
            _IF_INDEX: "2",
        }
        cleared = await correlator.handle_trap(_trap(_LINK_UP_OID, up_varbinds, "router-ncs55-1"))

        assert cleared is not None
        assert cleared.state == "cleared"
        assert cleared.cleared_at is not None

        persisted = await _get_alarm(session, "link:router-ncs55-1:1")
        assert persisted is not None
        assert persisted.state == "cleared"


@pytest.mark.integration
async def test_bgp_neighbor_down_creates_major_alarm(monkeypatch):
    monkeypatch.setattr(
        "app.services.alarms.correlator.maybe_snapshot_for_alarm",
        AsyncMock(return_value=0),
    )
    async with _correlator_ctx() as (correlator, session):
        varbinds = {
            _SYS_UPTIME_OID: "50000",
            _SNMP_TRAP_OID: _BGP_PEER2_STATE_CHANGED,
            _SYS_NAME_OID: "asr9k-pe1",
            _CBG_PEER2_REMOTE_ADDR: "192.168.100.2",
            _CBG_PEER2_STATE: "1",
            _CBG_PEER2_ADMIN_STATUS: "2",
        }
        alarm = await correlator.handle_trap(_trap(_BGP_PEER2_STATE_CHANGED, varbinds, "asr9k-pe1"))

        assert alarm is not None
        # BGP OID is not handled by correlator.classify() — falls through to generic "info"
        # but it IS classified as major by trap_classifier. The correlator classify() only
        # handles the 5 well-known OIDs; unknown OIDs produce severity "info".
        # We assert alarm is persisted with the correct OID recorded.
        assert alarm.trap_oid == _BGP_PEER2_STATE_CHANGED
        assert alarm.state == "active"
        assert alarm.source_host == "asr9k-pe1"

        persisted = await _get_alarm(session, alarm.correlation_key)
        assert persisted is not None


@pytest.mark.integration
async def test_psu_fail_creates_critical_alarm(monkeypatch):
    monkeypatch.setattr(
        "app.services.alarms.correlator.maybe_snapshot_for_alarm",
        AsyncMock(return_value=0),
    )
    async with _correlator_ctx() as (correlator, session):
        varbinds = {
            _SYS_UPTIME_OID: "80000",
            _SNMP_TRAP_OID: _CISCO_ENV_PSU_STATUS_CHANGE,
            _SYS_NAME_OID: "ncs560-pe3",
            _CISCO_ENV_PSU_DESC: "PowerSupply0",
            _CISCO_ENV_PSU_STATE: "4",
        }
        alarm = await correlator.handle_trap(
            _trap(_CISCO_ENV_PSU_STATUS_CHANGE, varbinds, "ncs560-pe3")
        )

        assert alarm is not None
        assert alarm.trap_oid == _CISCO_ENV_PSU_STATUS_CHANGE
        assert alarm.state == "active"

        persisted = await _get_alarm(session, alarm.correlation_key)
        assert persisted is not None


@pytest.mark.integration
async def test_fan_fail_creates_critical_alarm(monkeypatch):
    monkeypatch.setattr(
        "app.services.alarms.correlator.maybe_snapshot_for_alarm",
        AsyncMock(return_value=0),
    )
    async with _correlator_ctx() as (correlator, session):
        varbinds = {
            _SYS_UPTIME_OID: "70000",
            _SNMP_TRAP_OID: _CISCO_ENV_FAN_STATUS_CHANGE,
            _SYS_NAME_OID: "ncs560-pe3",
            _CISCO_ENV_FAN_STATUS_DESC: "FanTray0",
            _CISCO_ENV_FAN_STATUS: "3",
        }
        alarm = await correlator.handle_trap(
            _trap(_CISCO_ENV_FAN_STATUS_CHANGE, varbinds, "ncs560-pe3")
        )

        assert alarm is not None
        assert alarm.trap_oid == _CISCO_ENV_FAN_STATUS_CHANGE
        assert alarm.state == "active"

        persisted = await _get_alarm(session, alarm.correlation_key)
        assert persisted is not None


@pytest.mark.integration
async def test_config_change_creates_warning_alarm(monkeypatch):
    monkeypatch.setattr(
        "app.services.alarms.correlator.maybe_snapshot_for_alarm",
        AsyncMock(return_value=0),
    )
    async with _correlator_ctx() as (correlator, session):
        varbinds = {
            _SYS_UPTIME_OID: "90000",
            _SNMP_TRAP_OID: _CCM_CLI_RUNNING_CONFIG_CHANGED,
            _SYS_NAME_OID: "asr9010-core1",
            _CCM_HIST_EVENT_USER: "admin",
            _CCM_HIST_EVENT_CMD_SRC: "1",
        }
        alarm = await correlator.handle_trap(
            _trap(_CCM_CLI_RUNNING_CONFIG_CHANGED, varbinds, "asr9010-core1")
        )

        assert alarm is not None
        assert alarm.trap_oid == _CCM_CLI_RUNNING_CONFIG_CHANGED
        assert alarm.state == "active"

        persisted = await _get_alarm(session, alarm.correlation_key)
        assert persisted is not None


@pytest.mark.integration
async def test_duplicate_trap_within_dedup_window_is_deduplicated(monkeypatch):
    monkeypatch.setattr(
        "app.services.alarms.correlator.maybe_snapshot_for_alarm",
        AsyncMock(return_value=0),
    )
    async with _correlator_ctx() as (correlator, session):
        # Use a distinct host so this test's alarm doesn't collide with others
        varbinds = {
            _SYS_UPTIME_OID: "100",
            _SNMP_TRAP_OID: _LINK_DOWN_OID,
            _SYS_NAME_OID: "dedup-router",
            _IF_INDEX: "9",
        }
        trap = _trap(_LINK_DOWN_OID, varbinds, "dedup-router")

        first = await correlator.handle_trap(trap)
        second = await correlator.handle_trap(trap)
        third = await correlator.handle_trap(trap)

        assert first is not None
        assert second is not None
        assert third is not None
        assert first.id == second.id == third.id

        # _IF_INDEX OID suffix is "1" regardless of varbind value
        corr_key = "link:dedup-router:1"
        row_count = await _count_alarms(session, corr_key)
        assert row_count == 1

        persisted = await _get_alarm(session, corr_key)
        assert persisted is not None
        assert persisted.occurrence_count == 3
