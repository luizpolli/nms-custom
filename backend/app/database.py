"""Database engine and session factory for async SQLAlchemy."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy base for all models."""


async def get_db() -> AsyncSession:
    """Dependency: yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables and apply lightweight schema fixes for local upgrades."""
    from app import models  # noqa: F401 — import to register models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE IF EXISTS app_users ADD COLUMN IF NOT EXISTS custom_permissions JSON NOT NULL DEFAULT '{}'::json"))
        await conn.execute(text("ALTER TABLE IF EXISTS app_users ALTER COLUMN role TYPE VARCHAR(512)"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS site_id VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS role VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'active'"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS platform_family VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS mgmt_vrf VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS snmp_enabled BOOLEAN NOT NULL DEFAULT true"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS ssh_enabled BOOLEAN NOT NULL DEFAULT false"))
        await conn.execute(text("ALTER TABLE IF EXISTS devices ADD COLUMN IF NOT EXISTS telemetry_enabled BOOLEAN NOT NULL DEFAULT false"))
        await conn.execute(text("ALTER TABLE IF EXISTS kpis ADD COLUMN IF NOT EXISTS metric_name VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE IF EXISTS kpis ADD COLUMN IF NOT EXISTS source_type VARCHAR(30) NOT NULL DEFAULT 'snmp'"))
        await conn.execute(text("ALTER TABLE IF EXISTS kpis ADD COLUMN IF NOT EXISTS object_type VARCHAR(50) NOT NULL DEFAULT 'device'"))
        await conn.execute(text("ALTER TABLE IF EXISTS kpis ADD COLUMN IF NOT EXISTS object_id VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE IF EXISTS kpis ADD COLUMN IF NOT EXISTS quality VARCHAR(30) NOT NULL DEFAULT 'good'"))
        await conn.execute(text("ALTER TABLE IF EXISTS kpis ADD COLUMN IF NOT EXISTS labels JSON"))
        await conn.execute(text("ALTER TABLE IF EXISTS alarms ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE IF EXISTS alarms ADD COLUMN IF NOT EXISTS correlation_group_id UUID"))
        await conn.execute(text("ALTER TABLE IF EXISTS alarms ADD COLUMN IF NOT EXISTS root_alarm_id UUID"))
        await conn.execute(text("ALTER TABLE IF EXISTS alarms ADD COLUMN IF NOT EXISTS source_type VARCHAR(30) NOT NULL DEFAULT 'trap'"))
        await conn.execute(text("ALTER TABLE IF EXISTS alarms ADD COLUMN IF NOT EXISTS object_type VARCHAR(50)"))
        await conn.execute(text("ALTER TABLE IF EXISTS alarms ADD COLUMN IF NOT EXISTS object_id VARCHAR(255)"))


async def close_db() -> None:
    """Dispose engine connections."""
    await engine.dispose()
