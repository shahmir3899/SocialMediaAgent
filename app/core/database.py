"""Database engine and session management."""

import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import get_settings

settings = get_settings()

# Celery workers create a new asyncio event loop per task (run_async).
# Pooled asyncpg connections are bound to the loop that created them,
# causing "Future attached to a different loop" on subsequent tasks.
# NullPool avoids this by giving each session a fresh connection.
_use_null_pool = os.environ.get("USE_NULL_POOL", "").lower() in ("1", "true")

_pool_kwargs = (
    {"poolclass": NullPool}
    if _use_null_pool
    else {"pool_size": 20, "max_overflow": 10}
)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    **_pool_kwargs,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that provides an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
