"""Fixtures compartidos para toda la suite de tests."""

import pytest
from httpx import ASGITransport, AsyncClient
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


@pytest.fixture
async def client() -> AsyncClient:
    """Fixture que construye una app FastAPI mínima con las rutas de auth.

    Crea su propia base de datos SQLite en memoria y parchea el session_factory
    del auth_service singleton para que use la misma base de datos que la app.
    """
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.adapters.database.session import get_db
    from src.api.limiter import limiter
    from src.api.routes.admin_routes import router as admin_router
    from src.api.routes.auth_routes import router as auth_router
    from src.core.services.auth_service import auth_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(engine, expire_on_commit=False)
    # Parchear el auth_service singleton para que use la base de test
    auth_service._session_factory = test_factory

    limiter.reset()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)
    app.include_router(admin_router)

    async def _override_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()
