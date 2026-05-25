"""Tests for saved alarm filter endpoint handlers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.alarms import (
    SavedFilterCreate,
    SavedFilterUpdate,
    _alarm_filters_stmt,
    create_saved_alarm_filter,
    delete_saved_alarm_filter,
    list_saved_alarm_filters,
    update_saved_alarm_filter,
)
from app.models.alarm_filter import SavedAlarmFilter
from app.security.auth import Principal


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeDb:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.deleted = []

    async def execute(self, *args, **kwargs):
        return _Result(self.rows)

    def add(self, obj):
        self.rows.append(obj)

    async def flush(self):
        now = datetime.now(timezone.utc)
        for row in self.rows:
            if row.id is None:
                row.id = uuid.uuid4()
            if row.created_at is None:
                row.created_at = now
            if row.updated_at is None:
                row.updated_at = now

    async def refresh(self, obj):
        pass

    async def delete(self, obj):
        self.deleted.append(obj)
        self.rows.remove(obj)


def _principal(subject: str = "noc") -> Principal:
    return Principal(subject=subject, role="admin")


def _saved_filter(owner: str = "noc", public: bool = False) -> SavedAlarmFilter:
    now = datetime.now(timezone.utc)
    return SavedAlarmFilter(
        id=uuid.uuid4(),
        name="Core critical",
        owner=owner,
        is_public=public,
        filters={"severity": "critical", "q": "core"},
        created_at=now,
        updated_at=now,
    )


def test_alarm_filters_stmt_supports_interface_object_context():
    stmt = _alarm_filters_stmt(object_type="interface", object_id="iface-123")

    sql = str(stmt.whereclause)

    assert "object_type" in sql
    assert "object_id" in sql


@pytest.mark.asyncio
async def test_create_saved_alarm_filter_sets_owner_from_principal():
    db = FakeDb()
    result = await create_saved_alarm_filter(
        SavedFilterCreate(name="Core routers", filters={"severity": "major"}, is_public=True),
        db,  # type: ignore[arg-type]
        _principal("alice"),
    )

    assert result.owner == "alice"
    assert result.is_public is True
    assert result.filters == {"severity": "major"}
    assert result.can_update is True
    assert result.can_delete is True
    assert db.rows[0].owner == "alice"


@pytest.mark.asyncio
async def test_list_saved_alarm_filters_returns_model_payloads():
    owned = _saved_filter(owner="noc")
    public = _saved_filter(owner="ops", public=True)
    db = FakeDb([owned, public])

    result = await list_saved_alarm_filters(db, _principal("noc"))  # type: ignore[arg-type]

    assert [item.id for item in result] == [owned.id, public.id]
    assert result[0].filters["q"] == "core"
    assert result[0].can_update is True
    assert result[0].can_delete is True
    assert result[1].can_update is False


@pytest.mark.asyncio
async def test_update_saved_alarm_filter_owner_only():
    saved = _saved_filter(owner="noc")
    db = FakeDb([saved])

    result = await update_saved_alarm_filter(
        saved.id,
        SavedFilterUpdate(name="Updated", filters={"state": "active"}),
        db,  # type: ignore[arg-type]
        _principal("noc"),
    )

    assert result.name == "Updated"
    assert result.filters == {"state": "active"}


@pytest.mark.asyncio
async def test_update_saved_alarm_filter_rejects_non_owner():
    saved = _saved_filter(owner="noc")
    db = FakeDb([saved])

    with pytest.raises(HTTPException) as exc:
        await update_saved_alarm_filter(
            saved.id,
            SavedFilterUpdate(name="Nope"),
            db,  # type: ignore[arg-type]
            _principal("other"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_saved_alarm_filter_owner_can_promote_private_to_public():
    saved = _saved_filter(owner="noc", public=False)
    db = FakeDb([saved])

    result = await update_saved_alarm_filter(
        saved.id,
        SavedFilterUpdate(is_public=True),
        db,  # type: ignore[arg-type]
        _principal("noc"),
    )

    assert result.is_public is True
    assert result.can_update is True


@pytest.mark.asyncio
async def test_delete_saved_alarm_filter_admin_can_delete_any_filter():
    saved = _saved_filter(owner="other", public=True)
    db = FakeDb([saved])

    await delete_saved_alarm_filter(saved.id, db, _principal("noc"))  # type: ignore[arg-type]

    assert db.deleted == [saved]
    assert db.rows == []


@pytest.mark.asyncio
async def test_delete_saved_alarm_filter_rejects_non_admin():
    saved = _saved_filter(owner="noc")
    db = FakeDb([saved])

    with pytest.raises(HTTPException) as exc:
        await delete_saved_alarm_filter(
            saved.id,
            db,  # type: ignore[arg-type]
            Principal(subject="noc", role="operator"),
        )

    assert exc.value.status_code == 403
    assert db.deleted == []
