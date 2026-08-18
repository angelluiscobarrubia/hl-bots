"""Tests de integración del executor en BotManager."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.core.models import Base
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.bot_manager import BotManager
from src.core.services.strategy_manager import strategy_manager

STRATEGY_NAME = "SmaCrossoverStrategy"


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


@pytest.fixture
async def session_factory():
    """Factory de sesiones SQLite en memoria."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def adapter_factory() -> FakeAdapterFactory:
    """Factory de adapters falso."""
    return FakeAdapterFactory()


@pytest.fixture
def manager(session_factory, adapter_factory) -> BotManager:
    """BotManager con DB y factory de test."""
    return BotManager(session_factory=session_factory, adapter_factory=adapter_factory)


@pytest.fixture(autouse=True)
def _register_strategies():
    """Asegura que la estrategia de prueba esté registrada en el singleton."""
    strategy_manager.reload()
    yield


@pytest.fixture
async def running_bot(manager) -> int:
    """Crea y arranca un bot paper, devolviendo su id."""
    bot = await manager.create_bot(
        user_id=1,
        name="A",
        strategy=STRATEGY_NAME,
        config={"short_period": 2, "long_period": 3},
        is_paper=True,
    )
    await manager.start_bot(int(bot.id), None, None)
    return int(bot.id)


@pytest.mark.asyncio
async def test_start_bot_creates_executor(manager, running_bot) -> None:
    """Tras start_bot, el executor existe en _executors."""
    try:
        assert str(running_bot) in manager._executors
        assert manager._executors[str(running_bot)].is_running
    finally:
        await manager.stop_bot(running_bot)


@pytest.mark.asyncio
async def test_stop_bot_removes_executor(manager, running_bot) -> None:
    """Tras stop_bot, el executor se quita de _executors."""
    assert str(running_bot) in manager._executors
    await manager.stop_bot(running_bot)
    assert str(running_bot) not in manager._executors


@pytest.mark.asyncio
async def test_get_executor_returns_executor(manager, running_bot) -> None:
    """get_executor devuelve la instancia del executor activo."""
    try:
        executor = manager.get_executor(running_bot)
        assert executor is not None
        assert executor is manager._executors[str(running_bot)]
    finally:
        await manager.stop_bot(running_bot)


@pytest.mark.asyncio
async def test_get_executor_returns_none_for_stopped(manager, running_bot) -> None:
    """get_executor devuelve None para un bot detenido."""
    await manager.stop_bot(running_bot)
    assert manager.get_executor(running_bot) is None
