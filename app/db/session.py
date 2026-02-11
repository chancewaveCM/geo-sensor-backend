from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _is_postgresql(url: str) -> bool:
    """Check if the database URL is for PostgreSQL."""
    return url.startswith("postgresql")


def _build_engine_kwargs() -> dict:
    """Build engine kwargs based on database type."""
    kwargs: dict = {"echo": False}

    if _is_postgresql(settings.DATABASE_URL):
        kwargs["pool_size"] = settings.DB_POOL_SIZE
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        kwargs["pool_pre_ping"] = settings.DB_POOL_PRE_PING

    return kwargs


engine = create_async_engine(settings.DATABASE_URL, **_build_engine_kwargs())
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
