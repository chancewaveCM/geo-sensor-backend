import pytest
from contextlib import asynccontextmanager
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.session import engine
from app.models.base import Base


@asynccontextmanager
async def test_lifespan(app):
    """No-op lifespan for tests - skip schedulers and stuck job cleanup."""
    # Create tables for test DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    # Override lifespan for tests to avoid hanging schedulers
    app.router.lifespan_context = test_lifespan
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
