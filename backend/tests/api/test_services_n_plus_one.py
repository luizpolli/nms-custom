"""Regression test that proves list_services does NOT do N+1 (P1.7).

The bug we just fixed: ``_to_service_read`` reads
``ServiceDependency.source_service.name`` and ``target_service.name``.
Neither of those relationships had ``lazy="selectin"`` on the model, so
each dependency triggered two extra SELECTs per service. With 5 services
* 3 dependencies = 30 extra round-trips that vanish once the
``selectinload`` chain in ``list_services`` is in place.

This test seeds 5 services with 3 dependencies each into an in-memory
SQLite database, counts SELECT statements while ``list_services``
executes, and fails if the count grows linearly with N.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.service import Service, ServiceDependency, ServiceMember


# Number of services and dependencies-per-service to seed. Picked small
# enough to keep the test fast but large enough to make the N+1 vs flat
# query count visually obvious.
N_SERVICES = 5
DEPS_PER_SERVICE = 3


@pytest.fixture
async def db_engine():
    """In-memory SQLite engine with only the tables this test exercises.

    A full ``Base.metadata.create_all`` would try to render ``devices.tags``
    which is a Postgres ARRAY column SQLite can't compile. Filtering to the
    three Service-related tables avoids that without depending on a real
    Postgres in unit tests.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    tables = [
        Service.__table__,
        ServiceDependency.__table__,
        ServiceMember.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def seeded(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Seed N_SERVICES services, each with N member and DEPS_PER_SERVICE deps."""
    services: list[Service] = []
    async with session_factory() as session:
        for i in range(N_SERVICES):
            svc = Service(
                id=uuid.uuid4(),
                name=f"svc-{i:02d}",
                kind="logical",
                description=f"seed service {i}",
                target_score=95,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            svc.members.append(
                ServiceMember(
                    id=uuid.uuid4(),
                    service_id=svc.id,
                    device_id=None,
                    interface_id=None,
                    role="member",
                    weight=1.0,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.add(svc)
            services.append(svc)
        await session.commit()

        # Wire up deps: each service points to the next D services (wrapped).
        for i, svc in enumerate(services):
            for k in range(DEPS_PER_SERVICE):
                target = services[(i + k + 1) % N_SERVICES]
                dep = ServiceDependency(
                    id=uuid.uuid4(),
                    source_service_id=svc.id,
                    target_service_id=target.id,
                    dependency_type="hard",
                    direction="source_to_target",
                    direction_override="auto",
                    weight=1.0,
                    is_critical=False,
                    description=f"{svc.name}->{target.name}",
                    created_at=datetime.now(timezone.utc),
                )
                session.add(dep)
        await session.commit()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
) -> TestClient:
    """TestClient with the in-memory session injected for /api/services."""
    monkeypatch.setattr(settings, "api_auth_enabled", False)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    if prev is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = prev


def _make_select_counter() -> tuple[list[str], callable]:
    """Listener that records every SELECT statement issued on the engine."""
    selects: list[str] = []

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    return selects, _before_cursor_execute


@pytest.mark.usefixtures("seeded")
async def test_list_services_does_not_n_plus_one(
    client: TestClient, db_engine
) -> None:
    """Issued SELECT count must stay constant w.r.t. service count."""
    selects, listener = _make_select_counter()

    # ``before_cursor_execute`` fires on the sync DBAPI cursor, so we attach
    # to the underlying sync engine.
    event.listen(db_engine.sync_engine, "before_cursor_execute", listener)
    try:
        response = client.get("/api/services")
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", listener)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == N_SERVICES
    assert all(len(s["dependencies"]) == DEPS_PER_SERVICE for s in payload)
    assert all(s["dependencies"][0]["source_service_name"] for s in payload)
    assert all(s["dependencies"][0]["target_service_name"] for s in payload)

    # With the selectinload chain in place we expect a small constant
    # number of queries: 1 Service load + 1 selectin for members + 1 for
    # upstream_dependencies + 2 for source/target services on those deps.
    # Tolerate up to 8 to leave room for harmless prepared-statement
    # variations across SQLAlchemy versions.
    assert len(selects) <= 8, (
        f"Expected a small constant query count, got {len(selects)} SELECTs. "
        "list_services likely regressed back to N+1. SELECTs:\n  "
        + "\n  ".join(selects[:20])
    )

    # And it must definitely NOT scale with N_SERVICES * DEPS_PER_SERVICE.
    pathological = N_SERVICES * DEPS_PER_SERVICE
    assert len(selects) < pathological, (
        f"Query count {len(selects)} approaches the pathological "
        f"N*DEPS = {pathological}, which is the N+1 fingerprint."
    )
