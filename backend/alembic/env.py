"""Alembic environment using async SQLAlchemy + project Settings."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base
from app import models  # noqa: F401 — register all models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# Several existing revision IDs are longer than Alembic's default 32-char
# ``alembic_version.version_num`` column (e.g. ``0009_settings_system_
# network_alarms`` is 35 chars, ``0010_service_dependency_richer_modeling``
# is 39). On a fresh database Alembic creates the column at 32 chars and the
# very first insert truncates the revision id, blowing up CI.
#
# Fix: ensure the table exists at the wider width *before* Alembic gets a
# chance to auto-create it. ``CREATE TABLE IF NOT EXISTS`` makes this safe
# on already-migrated databases (the existing table wins and we ALTER its
# column width up). ``ALTER COLUMN ... TYPE`` is a no-op when the column is
# already wide enough.
_VERSION_TABLE_WIDTH = 64


def _ensure_wide_version_table(connection: Connection) -> None:
    from sqlalchemy import text

    connection.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS alembic_version ("
            f"  version_num VARCHAR({_VERSION_TABLE_WIDTH}) NOT NULL, "
            f"  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
            f")"
        )
    )
    try:
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                f"ALTER COLUMN version_num TYPE VARCHAR({_VERSION_TABLE_WIDTH})"
            )
        )
    except Exception:  # noqa: BLE001 -- non-Postgres backend or already widened
        pass


def do_run_migrations(connection: Connection) -> None:
    _ensure_wide_version_table(connection)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
