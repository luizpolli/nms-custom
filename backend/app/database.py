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


async def close_db() -> None:
    """Dispose engine connections."""
    await engine.dispose()
