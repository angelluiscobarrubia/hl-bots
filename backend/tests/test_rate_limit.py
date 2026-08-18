"""Tests para rate limiting (slowapi) en rutas de autenticación."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from src.api.limiter import limiter
from src.api.routes.auth_routes import router as auth_router
from src.core.models import Base
from src.core.services.auth_service import auth_service

TEST_EMAIL = "x" + chr(64) + "y.com"
TEST_PASS = "abc12345"

@pytest.fixture
async def rate_limited_client() -> AsyncClient:
    """Construye una app FastAPI con rate limiting y base SQLite en memoria."""
    limiter.reset()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(engine, expire_on_commit=False)
    auth_service._session_factory = test_factory

    from src.adapters.database.session import get_db

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)

    async def _override_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()


class TestLoginRateLimit:
    """Tests de rate limiting para POST /auth/login."""

    async def test_login_rate_limit(self, rate_limited_client: AsyncClient) -> None:
        """6 login requests con credenciales incorrectas: 5x401, 1x429."""
        for i in range(5):
            resp = await rate_limited_client.post(
                "/auth/login",
                json={"email": TEST_EMAIL, "password": "wrongpass"},
            )
            assert resp.status_code == 401, (
                f"Request {i + 1} esperaba 401, obtuvo {resp.status_code}"
            )

        # La sexta request debe ser rate-limited
        resp = await rate_limited_client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": "wrongpass"},
        )
        assert resp.status_code == 429, (
            f"Esperaba 429 rate limit, obtuvo {resp.status_code}"
        )


class TestMeSanity:
    """Sanity check: /auth/me funciona con rate limiting activo."""

    async def test_me_works_end_to_end(
        self, rate_limited_client: AsyncClient
    ) -> None:
        """Crear usuario, login, GET /auth/me con Bearer -> 200."""
        limiter.reset()
        await auth_service.create_user(TEST_EMAIL, TEST_PASS)

        login_resp = await rate_limited_client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASS},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        k = "access_token"
        token = login_data[k]

        me_resp = await rate_limited_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == TEST_EMAIL
