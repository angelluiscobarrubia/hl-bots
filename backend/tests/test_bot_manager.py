"""Tests para BotManager."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.core.entities.bot import BotStatus
from src.core.models import Base
from src.core.models import Bot as BotModel
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.bot_manager import BotManager


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
    """Factory falso que registra las llamadas y devuelve FakeAdapter."""

    def __init__(self) -> None:
        self.created: list[tuple] = []

    def create_adapter(self, bot, api_key_plaintext=None):
        self.created.append((bot, api_key_plaintext))
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


class TestCreateBot:
    """Tests de create_bot."""

    async def test_create_bot_persists_to_db(self, manager, session_factory):
        """create_bot guarda el bot en la DB."""
        await manager.create_bot(
            user_id=1,
            name="Bot A",
            strategy="sma_cross",
            config={"fast": 10},
            is_paper=True,
        )
        async with session_factory() as session:
            result = await session.execute(select(BotModel))
            db_bots = result.scalars().all()
        assert len(db_bots) == 1
        assert db_bots[0].name == "Bot A"
        assert db_bots[0].strategy_name == "sma_cross"
        assert db_bots[0].status == "stopped"

    async def test_create_bot_returns_entity(self, manager):
        """create_bot devuelve una entidad Bot con los campos correctos."""
        bot = await manager.create_bot(
            user_id=1,
            name="Bot A",
            strategy="sma_cross",
            config={"fast": 10},
            is_paper=True,
        )
        assert bot.id is not None
        assert bot.name == "Bot A"
        assert bot.strategy_name == "sma_cross"
        assert bot.is_paper is True
        assert bot.status == BotStatus.STOPPED
        assert bot.config == {"fast": 10}


class TestListBots:
    """Tests de list_bots."""

    async def test_list_bots_filters_by_user(self, manager):
        """list_bots solo devuelve los bots del usuario indicado."""
        await manager.create_bot(
            user_id=1, name="A", strategy="s", config={}, is_paper=True
        )
        await manager.create_bot(
            user_id=2, name="B", strategy="s", config={}, is_paper=True
        )
        bots_u1 = await manager.list_bots(user_id=1)
        bots_u2 = await manager.list_bots(user_id=2)
        assert len(bots_u1) == 1
        assert len(bots_u2) == 1
        assert bots_u1[0].name == "A"
        assert bots_u2[0].name == "B"


class TestStartBot:
    """Tests de start_bot."""

    async def test_start_paper_bot(self, manager, adapter_factory):
        """Arrancar un bot paper lo deja RUNNING y guarda el adapter."""
        bot = await manager.create_bot(
            user_id=1, name="A", strategy="s", config={}, is_paper=True
        )
        result = await manager.start_bot(int(bot.id), None, None)
        assert result is True
        assert str(bot.id) in manager._running_bots
        assert len(adapter_factory.created) == 1
        status = await manager.get_bot_status(int(bot.id))
        assert status == BotStatus.RUNNING

    async def test_start_real_bot_requires_keys(self, manager):
        """Arrancar un bot real sin API keys lanza ValueError."""
        bot = await manager.create_bot(
            user_id=1, name="A", strategy="s", config={}, is_paper=False
        )
        with pytest.raises(ValueError):
            await manager.start_bot(int(bot.id), None, None)

    async def test_start_real_bot_with_keys(self, manager, adapter_factory):
        """Arrancar un bot real con API keys funciona."""
        bot = await manager.create_bot(
            user_id=1, name="A", strategy="s", config={}, is_paper=False
        )
        result = await manager.start_bot(int(bot.id), "test-key", "test-secret")
        assert result is True
        assert str(bot.id) in manager._running_bots
        assert len(adapter_factory.created) == 1
        # El plaintext se pasa al factory (no se guarda en DB)
        _bot, plaintext = adapter_factory.created[0]
        assert plaintext is not None


class TestStopBot:
    """Tests de stop_bot."""

    async def test_stop_bot_updates_status(self, manager):
        """stop_bot quita el bot de _running_bots y actualiza su estado."""
        bot = await manager.create_bot(
            user_id=1, name="A", strategy="s", config={}, is_paper=True
        )
        await manager.start_bot(int(bot.id), None, None)
        assert str(bot.id) in manager._running_bots

        result = await manager.stop_bot(int(bot.id))
        assert result is True
        assert str(bot.id) not in manager._running_bots
        status = await manager.get_bot_status(int(bot.id))
        assert status == BotStatus.STOPPED


class TestGetBotStatus:
    """Tests de get_bot_status."""

    async def test_get_bot_status_returns_running_when_active(self, manager):
        """Devuelve RUNNING si el bot está en _running_bots."""
        bot = await manager.create_bot(
            user_id=1, name="A", strategy="s", config={}, is_paper=True
        )
        await manager.start_bot(int(bot.id), None, None)
        status = await manager.get_bot_status(int(bot.id))
        assert status == BotStatus.RUNNING

    async def test_get_bot_status_returns_db_status_when_stopped(self, manager):
        """Devuelve el estado de la DB si el bot no está activo."""
        bot = await manager.create_bot(
            user_id=1, name="A", strategy="s", config={}, is_paper=True
        )
        status = await manager.get_bot_status(int(bot.id))
        assert status == BotStatus.STOPPED
