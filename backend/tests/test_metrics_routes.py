"""Tests para las rutas /bots/{id}/metrics, /trades y /equity-curve."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.core.models import Base, Trade
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.bot_manager import BotManager
from src.core.services.metrics_service import MetricsService

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


async def _create_bot(client: AsyncClient, token: str) -> int:
    """Crea un bot paper y devuelve su id."""
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/bots",
        headers=headers,
        json={"name": "A", "strategy": "s", "is_paper": True},
    )
    assert created.status_code == 201, f"Create bot failed: {created.text}"
    return created.json()["id"]


async def _add_trades(factory, bot_id: int, user_id: int, trades: list[dict]) -> None:
    """Inserta trades directamente en la base de datos de test."""
    async with factory() as session:
        for t in trades:
            session.add(
                Trade(
                    bot_id=bot_id,
                    user_id=user_id,
                    symbol=t.get("symbol", "BTC-USD"),
                    side=t.get("side", "buy"),
                    price=t.get("price", 100.0),
                    quantity=t.get("quantity", 1.0),
                    pnl=t["pnl"],
                    executed_at=t.get("executed_at", datetime.utcnow()),
                )
            )
        await session.commit()


@pytest.fixture
async def metrics_env():
    """Cliente HTTP con routers de auth, bots y métricas + factory de DB."""
    import src.core.services.bot_manager as bm_module
    import src.core.services.metrics_service as ms_module
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.adapters.database.session import get_db
    from src.api.limiter import limiter
    from src.api.routes.auth_routes import router as auth_router
    from src.api.routes.bot_routes import router as bot_router
    from src.api.routes.metrics_routes import router as metrics_router
    from src.core.services.auth_service import auth_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(engine, expire_on_commit=False)
    auth_service._session_factory = test_factory

    # Patch de los singletons para usar la DB y el factory de test
    bm_module._bot_manager_instance = BotManager(
        session_factory=test_factory,
        adapter_factory=FakeAdapterFactory(),
    )
    ms_module._metrics_service_instance = MetricsService(session_factory=test_factory)

    await auth_service.create_user(USER1_EMAIL, USER_PASSWORD, role="user")
    await auth_service.create_user(USER2_EMAIL, USER_PASSWORD, role="user")

    limiter.reset()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)
    app.include_router(bot_router)
    app.include_router(metrics_router)

    async def _override_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield {"client": c, "factory": test_factory}

    await engine.dispose()


class TestMetricsRoutes:
    """Tests de las rutas de métricas."""

    async def test_get_metrics_empty(self, metrics_env):
        """Un bot sin trades devuelve métricas en cero."""
        client = metrics_env["client"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_bot(client, token)

        resp = await client.get(f"/bots/{bot_id}/metrics", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_id"] == bot_id
        assert data["total_trades"] == 0
        assert data["winning_trades"] == 0
        assert data["losing_trades"] == 0
        assert data["win_rate"] == 0.0
        assert data["total_pnl"] == 0.0
        assert data["avg_pnl"] == 0.0
        assert data["max_win"] == 0.0
        assert data["max_loss"] == 0.0
        assert data["sharpe_ratio"] is None

    async def test_get_metrics_with_trades(self, metrics_env):
        """Un bot con trades devuelve los agregados correctos."""
        client = metrics_env["client"]
        factory = metrics_env["factory"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_bot(client, token)

        await _add_trades(
            factory,
            bot_id,
            user_id=1,
            trades=[{"pnl": 10.0}, {"pnl": -4.0}, {"pnl": 6.0}],
        )

        resp = await client.get(f"/bots/{bot_id}/metrics", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 3
        assert data["winning_trades"] == 2
        assert data["losing_trades"] == 1
        assert data["total_pnl"] == pytest.approx(12.0)
        assert data["avg_pnl"] == pytest.approx(4.0)
        assert data["max_win"] == pytest.approx(10.0)
        assert data["max_loss"] == pytest.approx(-4.0)
        assert data["current_balance"] == pytest.approx(12.0)

    async def test_get_metrics_win_rate(self, metrics_env):
        """El win rate se calcula como ganadores / total."""
        client = metrics_env["client"]
        factory = metrics_env["factory"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_bot(client, token)

        await _add_trades(
            factory,
            bot_id,
            user_id=1,
            trades=[{"pnl": 5.0}, {"pnl": 3.0}, {"pnl": -2.0}],
        )

        resp = await client.get(f"/bots/{bot_id}/metrics", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["win_rate"] == pytest.approx(2 / 3)

    async def test_get_metrics_sharpe_ratio(self, metrics_env):
        """El Sharpe ratio simplificado es mean(pnl) / std(pnl)."""
        client = metrics_env["client"]
        factory = metrics_env["factory"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_bot(client, token)

        # mean=4, stdev=2 -> sharpe = 2.0
        await _add_trades(
            factory,
            bot_id,
            user_id=1,
            trades=[{"pnl": 2.0}, {"pnl": 4.0}, {"pnl": 6.0}],
        )

        resp = await client.get(f"/bots/{bot_id}/metrics", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["sharpe_ratio"] == pytest.approx(2.0)

    async def test_get_trades_paginated(self, metrics_env):
        """La paginación de trades funciona con limit y offset."""
        client = metrics_env["client"]
        factory = metrics_env["factory"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_bot(client, token)

        base = datetime(2026, 1, 1, 12, 0, 0)
        await _add_trades(
            factory,
            bot_id,
            user_id=1,
            trades=[
                {"pnl": 1.0, "executed_at": base + timedelta(minutes=i)}
                for i in range(5)
            ],
        )

        resp = await client.get(
            f"/bots/{bot_id}/trades?limit=2&offset=0", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        resp2 = await client.get(
            f"/bots/{bot_id}/trades?limit=2&offset=2", headers=headers
        )
        assert resp2.status_code == 200
        assert len(resp2.json()) == 2

    async def test_get_trades_ordered_by_date(self, metrics_env):
        """Los trades se devuelven del más reciente al más antiguo."""
        client = metrics_env["client"]
        factory = metrics_env["factory"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_bot(client, token)

        base = datetime(2026, 1, 1, 12, 0, 0)
        await _add_trades(
            factory,
            bot_id,
            user_id=1,
            trades=[
                {"pnl": 1.0, "executed_at": base + timedelta(minutes=1)},
                {"pnl": 2.0, "executed_at": base + timedelta(minutes=2)},
                {"pnl": 3.0, "executed_at": base + timedelta(minutes=3)},
            ],
        )

        resp = await client.get(f"/bots/{bot_id}/trades", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert [t["pnl"] for t in data] == [3.0, 2.0, 1.0]

    async def test_get_equity_curve(self, metrics_env):
        """La curva de equity acumula el P&L en orden cronológico."""
        client = metrics_env["client"]
        factory = metrics_env["factory"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}
        bot_id = await _create_bot(client, token)

        base = datetime(2026, 1, 1, 12, 0, 0)
        await _add_trades(
            factory,
            bot_id,
            user_id=1,
            trades=[
                {"pnl": 10.0, "executed_at": base},
                {"pnl": -5.0, "executed_at": base + timedelta(minutes=1)},
                {"pnl": 20.0, "executed_at": base + timedelta(minutes=2)},
            ],
        )

        resp = await client.get(f"/bots/{bot_id}/equity-curve", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_id"] == bot_id
        assert [p["equity"] for p in data["points"]] == [10.0, 5.0, 25.0]

    async def test_unauthorized_user_cannot_access(self, metrics_env):
        """Un usuario ajeno no puede consultar las métricas de otro bot."""
        client = metrics_env["client"]
        token1 = await _login(client, USER1_EMAIL, USER_PASSWORD)
        token2 = await _login(client, USER2_EMAIL, USER_PASSWORD)
        h2 = {"Authorization": f"Bearer {token2}"}
        bot_id = await _create_bot(client, token1)

        resp = await client.get(f"/bots/{bot_id}/metrics", headers=h2)
        assert resp.status_code == 403

    async def test_metrics_for_nonexistent_bot(self, metrics_env):
        """Consultar métricas de un bot inexistente devuelve 404."""
        client = metrics_env["client"]
        token = await _login(client, USER1_EMAIL, USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/bots/999/metrics", headers=headers)
        assert resp.status_code == 404
