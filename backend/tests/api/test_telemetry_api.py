"""Telemetry API behavior tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException, status

from app.api.telemetry import _ensure_unique_collector_name


class _FakeResult:
    def __init__(self, value: uuid.UUID | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> uuid.UUID | None:
        return self.value


class _FakeSession:
    def __init__(self, value: uuid.UUID | None) -> None:
        self.value = value

    async def execute(self, *args, **kwargs) -> _FakeResult:
        return _FakeResult(self.value)


async def test_ensure_unique_collector_name_rejects_duplicate() -> None:
    with pytest.raises(HTTPException) as exc:
        await _ensure_unique_collector_name(_FakeSession(uuid.uuid4()), "local-json-telemetry-sim")  # type: ignore[arg-type]

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert exc.value.detail == "Telemetry collector name already exists"


async def test_ensure_unique_collector_name_allows_new_name() -> None:
    await _ensure_unique_collector_name(_FakeSession(None), "new-collector")  # type: ignore[arg-type]
