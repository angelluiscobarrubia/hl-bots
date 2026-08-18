"""Tests para RiskManager."""

from __future__ import annotations

import pytest
from src.adapters.hyperliquid.paper_broker_adapter import PaperBrokerAdapter
from src.core.entities.bot import Bot
from src.core.entities.order import OrderSide
from src.core.services.risk_manager import RiskManager


def make_bot(config: dict | None = None) -> Bot:
    """Crea un bot de prueba."""
    return Bot(
        id="1",
        user_id="1",
        name="bot",
        strategy_name="sma_crossover",
        symbol="BTC-USD",
        config=config or {},
    )


@pytest.mark.asyncio
async def test_validate_order_within_position_limit() -> None:
    """Una orden dentro del 25% del balance pasa la validación."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 1.0, 100.0)
    assert ok is True
    assert reason == "OK"


@pytest.mark.asyncio
async def test_validate_order_exceeds_position_limit() -> None:
    """Una orden que supera el 25% del balance es rechazada."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    # 30 * 100 = 3000 > 10000 * 0.25 = 2500
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 30.0, 100.0)
    assert ok is False
    assert "position" in reason.lower()


@pytest.mark.asyncio
async def test_validate_order_daily_loss_exceeded() -> None:
    """Tras perder más del 5% del balance inicial, las órdenes se rechazan."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    await rm._load_balance()  # starting_balance = 10000
    rm._daily_pnl = -600.0  # 6% > 5%
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 1.0, 100.0)
    assert ok is False
    assert "daily" in reason.lower()


@pytest.mark.asyncio
async def test_validate_order_drawdown_exceeded() -> None:
    """Tras un drawdown superior al 15%, las órdenes se rechazan."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    await rm._load_balance()  # peak = 10000
    rm._peak_balance = 20000.0  # drawdown = (20000-10000)/20000 = 50%
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 1.0, 100.0)
    assert ok is False
    assert "drawdown" in reason.lower()


@pytest.mark.asyncio
async def test_validate_order_max_positions_exceeded() -> None:
    """Con 3 posiciones abiertas, una 4ª orden es rechazada."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    rm._positions = {
        "BTC-USD": {"side": OrderSide.BUY, "quantity": 1.0, "entry_price": 100.0},
        "ETH-USD": {"side": OrderSide.BUY, "quantity": 1.0, "entry_price": 100.0},
        "SOL-USD": {"side": OrderSide.BUY, "quantity": 1.0, "entry_price": 100.0},
    }
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 1.0, 100.0)
    assert ok is False
    assert "positions" in reason.lower()


@pytest.mark.asyncio
async def test_validate_order_stop_loss_triggered() -> None:
    """Con stop loss activo y pérdida superior al límite, se rechaza el BUY."""
    bot = make_bot(config={"risk_config": {"stop_loss_pct": 0.05}})
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(bot, adapter)
    rm._positions = {
        "BTC-USD": {"side": OrderSide.BUY, "quantity": 1.0, "entry_price": 100.0}
    }
    # Precio 90 -> pérdida del 10% > 5% stop loss
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 1.0, 90.0)
    assert ok is False
    assert "stop loss" in reason.lower()


@pytest.mark.asyncio
async def test_record_trade_updates_daily_pnl() -> None:
    """Tras vender con pérdida, el P&L diario queda negativo."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    buy = await adapter.place_order("BTC-USD", OrderSide.BUY, 1.0, price=100.0)
    await rm.record_trade(buy)
    sell = await adapter.place_order("BTC-USD", OrderSide.SELL, 1.0, price=90.0)
    await rm.record_trade(sell)
    assert rm._daily_pnl == pytest.approx(-10.0)


@pytest.mark.asyncio
async def test_record_trade_updates_peak_balance() -> None:
    """Tras un trade rentable, el balance pico se actualiza."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    await rm._load_balance()  # peak = 10000
    buy = await adapter.place_order("BTC-USD", OrderSide.BUY, 1.0, price=100.0)
    await rm.record_trade(buy)
    sell = await adapter.place_order("BTC-USD", OrderSide.SELL, 1.0, price=150.0)
    await rm.record_trade(sell)
    # balance = 10000 - 100 + 150 = 10050
    assert rm._peak_balance == pytest.approx(10050.0)


@pytest.mark.asyncio
async def test_halt_blocks_all_orders() -> None:
    """Tras halt(), todas las órdenes se rechazan."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    rm.halt("test halt")
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 1.0, 100.0)
    assert ok is False
    assert reason == "test halt"


@pytest.mark.asyncio
async def test_resume_allows_orders() -> None:
    """Tras resume(), las órdenes vuelven a permitirse."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    rm = RiskManager(make_bot(), adapter)
    rm.halt("test halt")
    rm.resume()
    ok, reason = await rm.validate_order("BTC-USD", OrderSide.BUY, 1.0, 100.0)
    assert ok is True
    assert reason == "OK"
