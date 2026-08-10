"""Fixtures compartidos para toda la suite de tests."""

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.core.models import Base


@pytest.fixture
async def db_session() -> AsyncSession:
    """Fixture que provee una sesión SQLite en memoria con esquema creado."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
