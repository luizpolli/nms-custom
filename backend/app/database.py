"""Database engine and session factory for async SQLAlchemy."""

from collections.abc import AsyncGenerator

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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Ensure ORM-declared tables exist (dev/embedded fallback).

    Alembic migrations (``alembic upgrade head``) are the canonical schema
    source. This helper runs ``create_all`` and then performs best-effort
    TimescaleDB setup for local/Compose deployments that skip migrations.
    """
    from app import models  # noqa: F401 — import to register models
    from app.services.retention import ensure_timescale_schema

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await ensure_timescale_schema(session)
        await session.commit()


async def close_db() -> None:
    """Dispose engine connections."""
    await engine.dispose()
