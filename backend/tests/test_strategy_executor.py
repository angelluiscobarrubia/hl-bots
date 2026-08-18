"""Tests para StrategyExecutor."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from src.adapters.hyperliquid.paper_broker_adapter import PaperBrokerAdapter
from src.core.entities.bot import Bot
from src.core.entities.order import OrderSide
from src.core.ports.i_strategy import IStrategy, Signal
from src.core.services.strategy_executor import StrategyExecutor


class FakeStrategy(IStrategy):
    """Estrategia stub que devuelve una señal fija (o lanza en la 1ª llamada)."""

    def __init__(
        self,
        signal: Signal | None = None,
        fail_first: bool = False,
    ) -> None:
        self.signal = signal
        self.fail_first = fail_first
        self.calls = 0

    async def analyze(self, market_data: dict[str, Any]) -> Signal | None:
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise RuntimeError("boom")
        return self.signal

    def get_required_params(self) -> dict[str, Any]:
        return {}


def make_bot() -> Bot:
    """Crea un bot de prueba."""
    return Bot(
        id="1",
        user_id="1",
        name="bot",
        strategy_name="sma_crossover",
        symbol="BTC-USD",
        config={},
    )


@pytest.mark.asyncio
async def test_run_once_no_signal() -> None:
    """Si la estrategia devuelve None, no se coloca ninguna orden."""
    adapter = PaperBrokerAdapter()
    executor = StrategyExecutor(
        bot=make_bot(), adapter=adapter, strategy=FakeStrategy(signal=None)
    )
    await executor.run_once()
    assert executor.trades == []
    assert adapter._order_history == []


@pytest.mark.asyncio
async def test_run_once_buy_signal_places_order() -> None:
    """Una señal BUY coloca una orden de compra."""
    adapter = PaperBrokerAdapter()
    executor = StrategyExecutor(
        bot=make_bot(),
        adapter=adapter,
        strategy=FakeStrategy(signal=Signal(action=OrderSide.BUY, quantity=1.0)),
    )
    await executor.run_once()
    assert len(executor.trades) == 1
    assert executor.trades[0].side == OrderSide.BUY
    assert executor.trades[0].quantity == 1.0


@pytest.mark.asyncio
async def test_run_once_sell_signal_places_order() -> None:
    """Una señal SELL coloca una orden de venta."""
    adapter = PaperBrokerAdapter()
    executor = StrategyExecutor(
        bot=make_bot(),
        adapter=adapter,
        strategy=FakeStrategy(signal=Signal(action=OrderSide.SELL, quantity=1.0)),
    )
    await executor.run_once()
    assert len(executor.trades) == 1
    assert executor.trades[0].side == OrderSide.SELL


@pytest.mark.asyncio
async def test_run_once_uses_signal_quantity() -> None:
    """Si la señal trae cantidad, se usa esa cantidad."""
    adapter = PaperBrokerAdapter()
    executor = StrategyExecutor(
        bot=make_bot(),
        adapter=adapter,
        strategy=FakeStrategy(signal=Signal(action=OrderSide.BUY, quantity=2.5)),
    )
    await executor.run_once()
    assert len(executor.trades) == 1
    assert executor.trades[0].quantity == 2.5


@pytest.mark.asyncio
async def test_run_once_calculates_default_quantity() -> None:
    """Si la señal no trae cantidad, se calcula 10% del balance / precio."""
    adapter = PaperBrokerAdapter(initial_balance=10000.0)
    executor = StrategyExecutor(
        bot=make_bot(),
        adapter=adapter,
        strategy=FakeStrategy(signal=Signal(action=OrderSide.BUY, quantity=None)),
    )
    await executor.run_once()
    assert len(executor.trades) == 1
    candles = await adapter.get_ohlcv("BTC-USD", interval="1m", limit=100)
    current_price = candles[-1]["close"]
    expected = (10000.0 * 0.1) / current_price
    assert executor.trades[0].quantity == pytest.approx(expected)


@pytest.mark.asyncio
async def test_run_forever_stops_on_stop() -> None:
    """El bucle corre varias iteraciones y se detiene con stop()."""
    adapter = PaperBrokerAdapter()
    executor = StrategyExecutor(
        bot=make_bot(),
        adapter=adapter,
        strategy=FakeStrategy(signal=Signal(action=OrderSide.BUY, quantity=1.0)),
    )
    task = asyncio.create_task(executor.run_forever(interval_seconds=1))
    await asyncio.sleep(2.5)
    assert executor.is_running
    assert len(executor.trades) >= 1
    executor.stop()
    await asyncio.wait_for(task, timeout=3)
    assert not executor.is_running


@pytest.mark.asyncio
async def test_run_forever_handles_exceptions() -> None:
    """Un error en una iteración no detiene el bucle."""
    adapter = PaperBrokerAdapter()
    strategy = FakeStrategy(
        signal=Signal(action=OrderSide.BUY, quantity=1.0), fail_first=True
    )
    executor = StrategyExecutor(bot=make_bot(), adapter=adapter, strategy=strategy)
    task = asyncio.create_task(executor.run_forever(interval_seconds=1))
    await asyncio.sleep(2.5)
    executor.stop()
    await asyncio.wait_for(task, timeout=3)
    # La primera iteración falló, pero las siguientes colocaron órdenes.
    assert strategy.calls >= 2
    assert len(executor.trades) >= 1


@pytest.mark.asyncio
async def test_trades_are_tracked() -> None:
    """Tras colocar órdenes, el historial de trades las contiene."""
    adapter = PaperBrokerAdapter()
    executor = StrategyExecutor(
        bot=make_bot(),
        adapter=adapter,
        strategy=FakeStrategy(signal=Signal(action=OrderSide.BUY, quantity=1.0)),
    )
    await executor.run_once()
    await executor.run_once()
    assert len(executor.trades) == 2
    assert all(t.side == OrderSide.BUY for t in executor.trades)
