"""Tests para las rutas /bots."""

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
        return 0.0

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


@pytest.fixture
async def bot_client():
    """Cliente HTTP con router de bots y usuarios pre-creados."""
    import src.core.services.bot_manager as bm_module
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.adapters.database.session import get_db
    from src.api.limiter import limiter
    from src.api.routes.auth_routes import router as auth_router
    from src.api.routes.bot_routes import router as bot_router
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

    # Crear usuarios directamente via el servicio (no por HTTP)
    await auth_service.create_user(USER1_EMAIL, USER_PASSWORD, role="user")
    await auth_service.create_user(USER2_EMAIL, USER_PASSWORD, role="user")

    limiter.reset()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)
    app.include_router(bot_router)

    async def _override_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()


class TestBotRoutes:
    """Tests de las rutas /bots."""

    async def test_create_bot_as_user(self, bot_client):
        """Un usuario autenticado puede crear un bot (201)."""
        token = await _login(bot_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await bot_client.post(
            "/bots",
            headers=headers,
            json={
                "name": "My Bot",
                "strategy": "sma_cross",
                "symbol": "BTC-USD",
                "is_paper": True,
                "config": {"fast": 10},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Bot"
        assert data["strategy_name"] == "sma_cross"
        assert data["is_paper"] is True
        assert data["status"] == "stopped"
        assert data["user_id"] == 1

    async def test_create_bot_unauthenticated(self, bot_client):
        """Sin token devuelve 401."""
        resp = await bot_client.post(
            "/bots", json={"name": "B", "strategy": "s"}
        )
        assert resp.status_code == 401

    async def test_list_bots_returns_user_bots(self, bot_client):
        """GET /bots solo devuelve los bots del usuario autenticado."""
        token1 = await _login(bot_client, USER1_EMAIL, USER_PASSWORD)
        token2 = await _login(bot_client, USER2_EMAIL, USER_PASSWORD)
        h1 = {"Authorization": f"Bearer {token1}"}
        h2 = {"Authorization": f"Bearer {token2}"}
        await bot_client.post("/bots", headers=h1, json={"name": "A", "strategy": "s"})
        await bot_client.post("/bots", headers=h1, json={"name": "B", "strategy": "s"})
        await bot_client.post("/bots", headers=h2, json={"name": "C", "strategy": "s"})

        resp = await bot_client.get("/bots", headers=h1)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert {b["name"] for b in data["bots"]} == {"A", "B"}

    async def test_get_bot_by_id(self, bot_client):
        """GET /bots/{id} devuelve los detalles del bot."""
        token = await _login(bot_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        created = await bot_client.post(
            "/bots", headers=headers, json={"name": "A", "strategy": "s"}
        )
        bot_id = created.json()["id"]

        resp = await bot_client.get(f"/bots/{bot_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "A"

    async def test_get_other_users_bot_forbidden(self, bot_client):
        """GET /bots/{id} de un bot ajeno devuelve 403."""
        token1 = await _login(bot_client, USER1_EMAIL, USER_PASSWORD)
        token2 = await _login(bot_client, USER2_EMAIL, USER_PASSWORD)
        h1 = {"Authorization": f"Bearer {token1}"}
        h2 = {"Authorization": f"Bearer {token2}"}
        created = await bot_client.post(
            "/bots", headers=h1, json={"name": "A", "strategy": "s"}
        )
        bot_id = created.json()["id"]

        resp = await bot_client.get(f"/bots/{bot_id}", headers=h2)
        assert resp.status_code == 403

    async def test_start_paper_bot(self, bot_client):
        """POST /bots/{id}/start arranca un bot paper."""
        token = await _login(bot_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        created = await bot_client.post(
            "/bots",
            headers=headers,
            json={"name": "A", "strategy": "s", "is_paper": True},
        )
        bot_id = created.json()["id"]

        resp = await bot_client.post(f"/bots/{bot_id}/start", headers=headers, json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    async def test_start_real_bot_without_keys_fails(self, bot_client):
        """POST /bots/{id}/start de un bot real sin keys devuelve 400."""
        token = await _login(bot_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        created = await bot_client.post(
            "/bots",
            headers=headers,
            json={"name": "A", "strategy": "s", "is_paper": False},
        )
        bot_id = created.json()["id"]

        resp = await bot_client.post(f"/bots/{bot_id}/start", headers=headers, json={})
        assert resp.status_code == 400

    async def test_stop_bot(self, bot_client):
        """POST /bots/{id}/stop detiene un bot."""
        token = await _login(bot_client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        created = await bot_client.post(
            "/bots",
            headers=headers,
            json={"name": "A", "strategy": "s", "is_paper": True},
        )
        bot_id = created.json()["id"]
        await bot_client.post(f"/bots/{bot_id}/start", headers=headers, json={})

        resp = await bot_client.post(f"/bots/{bot_id}/stop", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"
