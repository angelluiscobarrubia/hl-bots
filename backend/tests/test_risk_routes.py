"""Tests para las rutas /bots/{id}/risk."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.core.models import Base
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.bot_manager import BotManager

USER1_EMAIL = "user1" + "@" + "example.com"
USER2_EMAIL = "user2" + "@" + "example.com"
USER_PASSWORD = "user" + "pass" + "123"


class FakeAdapter(IHyperliquidAdapter):
    """Adapter stub para tests."""

    async def connect(self) -> None:
        return None

    async def get_balance(self, asset: str = "USDC") -> float:
        return 10000.0

    async def get_ohlcv(
        self, symbol: str, interval: str = "1m", limit: int = 100
    ) -> list[dict]:
        return []

    async def place_order(
        self,
        symbol: str,
        side,
        quantity: float,
        price: float | None = None,
        is_reduce_only: bool = False,
    ):
        return None

    async def close_position(self, symbol: str):
        return None

    async def subscribe_market_data(self, symbol: str, callback) -> None:
        return None


class FakeAdapterFactory:
    """Factory falso que devuelve FakeAdapter."""

    def create_adapter(self, bot, api_key_plaintext=None):
        return FakeAdapter()


async def _login(client: AsyncClient, email: str, password: str) -> str:
    """Hace login y devuelve el access_token."""
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


async def _create_and_start_bot(client: AsyncClient, token: str) -> int:
    """Crea y arranca un bot paper, devolviendo su id."""
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/bots",
        headers=headers,
        json={"name": "A", "strategy": "s", "is_paper": True},
    )
    assert created.status_code == 201, f"Create bot failed: {created.text}"
    bot_id = created.json()["id"]
    started = await client.post(f"/bots/{bot_id}/start", headers=headers, json={})
    assert started.status_code == 200, f"Start bot failed: {started.text}"
    return bot_id


@pytest.fixture
async def risk_client():
    """Cliente HTTP con routers de bots y riesgo y usuarios pre-creados."""
    import src.core.services.bot_manager as bm_module
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.adapters.database.session import get_db
    from src.api.limiter import limiter
    from src.api.routes.auth_routes import router as auth_router
    from src.api.routes.bot_routes import router as bot_router
    from src.api.routes.risk_routes import router as risk_router
    from src.core.services.auth_service import auth_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(engine, expire_on_commit=False)
    auth_service._session_factory = test_factory

    # Patch del singleton del BotManager para usar la DB y el factory de test
    bm_module._bot_manager_instance = BotManager(
        session_factory=test_factory,
        adapter_factory=FakeAdapterFactory(),
    )

    await auth_service.create_user(USER1_EMAIL, USER_PASSWORD, role="user")
    await auth_service.create_user(USER2_EMAIL, USER_PASSWORD, role="user")

    limiter.reset()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)
    app.include_router(bot_router)
    app.include_router(risk_router)

    async def _override_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()


class TestRiskRoutes:
    """Tests de las rutas /bots/{id}/risk."""

    async def test_get_risk_status(self, risk_client):
        """GET /bots/{id}/risk/status devuelve el estado de riesgo."""
        token = await _login(risk_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_and_start_bot(risk_client, token)

        resp = await risk_client.get(f"/bots/{bot_id}/risk/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_id"] == bot_id
        assert data["is_halted"] is False
        assert data["current_balance"] == 10000.0
        assert data["starting_balance"] == 10000.0
        assert data["open_positions"] == 0

    async def test_get_risk_status_forbidden(self, risk_client):
        """GET /bots/{id}/risk/status de un bot ajeno devuelve 403."""
        token1 = await _login(risk_client, USER1_EMAIL, USER_PASSWORD)
        token2 = await _login(risk_client, USER2_EMAIL, USER_PASSWORD)
        h2 = {"Authorization": f"Bearer {token2}"}
        bot_id = await _create_and_start_bot(risk_client, token1)

        resp = await risk_client.get(f"/bots/{bot_id}/risk/status", headers=h2)
        assert resp.status_code == 403

    async def test_halt_bot(self, risk_client):
        """POST /bots/{id}/risk/halt detiene el trading."""
        token = await _login(risk_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_and_start_bot(risk_client, token)

        resp = await risk_client.post(f"/bots/{bot_id}/risk/halt", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_halted"] is True
        assert data["halt_reason"] is not None

    async def test_resume_bot(self, risk_client):
        """POST /bots/{id}/risk/resume reanuda el trading."""
        token = await _login(risk_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_and_start_bot(risk_client, token)

        await risk_client.post(f"/bots/{bot_id}/risk/halt", headers=headers)
        resp = await risk_client.post(f"/bots/{bot_id}/risk/resume", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_halted"] is False
        assert data["halt_reason"] is None
