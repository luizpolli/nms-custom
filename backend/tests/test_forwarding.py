"""Tests for event forwarding target CRUD and probe endpoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.forwarding import ForwardingTarget


@pytest.fixture()
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: ForwardingTarget.__table__.create(sync_conn))
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture()
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[TestClient, None]:
    async def _db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _db
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def mock_udp_socket(monkeypatch: pytest.MonkeyPatch) -> Generator[MagicMock, None, None]:
    sock = MagicMock()
    sock.__enter__.return_value = sock
    sock.__exit__.return_value = None
    factory = MagicMock(return_value=sock)
    monkeypatch.setattr("app.services.forwarding.engine.socket.socket", factory)
    yield sock


def _payload(name: str = "noc-upstream") -> dict:
    return {
        "name": name,
        "protocol": "syslog_udp",
        "target_host": "127.0.0.1",
        "target_port": 5514,
        "event_types": ["trap", "syslog", "alarm"],
        "severity_filter": "warning",
        "enabled": True,
    }


def _account_audit_payload(name: str = "secops-upstream") -> dict:
    payload = _payload(name)
    payload["event_types"] = ["account_audit"]
    payload["severity_filter"] = None
    return payload


def test_forwarding_crud(client: TestClient) -> None:
    create = client.post("/api/forwarding/targets", json=_payload())
    assert create.status_code == 201
    target = create.json()
    assert target["name"] == "noc-upstream"
    assert target["protocol"] == "syslog_udp"

    listed = client.get("/api/forwarding/targets")
    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()] == ["noc-upstream"]

    fetched = client.get(f"/api/forwarding/targets/{target['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["target_host"] == "127.0.0.1"

    patched = client.patch(
        f"/api/forwarding/targets/{target['id']}",
        json={"enabled": False, "severity_filter": "critical"},
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False
    assert patched.json()["severity_filter"] == "critical"

    deleted = client.delete(f"/api/forwarding/targets/{target['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/forwarding/targets").json() == []


def test_duplicate_name_rejected(client: TestClient) -> None:
    assert client.post("/api/forwarding/targets", json=_payload()).status_code == 201
    duplicate = client.post("/api/forwarding/targets", json=_payload())
    assert duplicate.status_code == 409


def test_test_endpoint_sends_udp_probe(client: TestClient, mock_udp_socket: MagicMock) -> None:
    target = client.post("/api/forwarding/targets", json=_payload()).json()
    response = client.post(f"/api/forwarding/targets/{target['id']}/test")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    mock_udp_socket.sendto.assert_called_once()
    payload, destination = mock_udp_socket.sendto.call_args.args
    assert b"NMS Custom forwarding test event" in payload
    assert destination == ("127.0.0.1", 5514)


def test_account_audit_event_type_is_valid(client: TestClient) -> None:
    response = client.post("/api/forwarding/targets", json=_account_audit_payload())
    assert response.status_code == 201
    assert response.json()["event_types"] == ["account_audit"]


def test_invalid_port_and_host_validation(client: TestClient) -> None:
    bad_port = client.post("/api/forwarding/targets", json={**_payload(), "target_port": 70000})
    assert bad_port.status_code == 422

    bad_host = client.post("/api/forwarding/targets", json={**_payload("bad-host"), "target_host": "bad host"})
    assert bad_host.status_code == 422

    no_events = client.post("/api/forwarding/targets", json={**_payload("no-events"), "event_types": []})
    assert no_events.status_code == 422
