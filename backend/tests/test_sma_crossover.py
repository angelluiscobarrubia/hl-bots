"""Tests para SmaCrossoverStrategy."""

from __future__ import annotations

from typing import Any

import pytest
from src.core.entities.order import OrderSide
from src.core.ports.i_strategy import Signal
from strategies.sma_crossover import SmaCrossoverStrategy


def make_strategy(config: dict[str, Any] | None = None) -> SmaCrossoverStrategy:
    """Crea una estrategia con config opcional."""
    return SmaCrossoverStrategy(config or {})


def market_data(closes: list[float]) -> dict[str, Any]:
    """Construye market_data con la clave ``closes``."""
    return {"closes": closes}


@pytest.mark.asyncio
async def test_init_with_defaults() -> None:
    """Los periodos por defecto son 10 y 20."""
    strategy = make_strategy()
    assert strategy.short_period == 10
    assert strategy.long_period == 20
    assert strategy.quantity == 0.1


@pytest.mark.asyncio
async def test_init_with_custom_config() -> None:
    """Los periodos se leen de la config."""
    strategy = make_strategy({"short_period": 5, "long_period": 15, "quantity": 0.5})
    assert strategy.short_period == 5
    assert strategy.long_period == 15
    assert strategy.quantity == 0.5


@pytest.mark.asyncio
async def test_analyze_no_crossover_returns_none() -> None:
    """Sin cruce, analyze devuelve None."""
    strategy = make_strategy({"short_period": 2, "long_period": 3})
    closes = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    signal = await strategy.analyze(market_data(closes))
    assert signal is None


@pytest.mark.asyncio
async def test_analyze_bullish_crossover_returns_buy() -> None:
    """La corta cruza por encima de la larga -> BUY."""
    strategy = make_strategy({"short_period": 2, "long_period": 3})
    closes = [10.0, 10.0, 10.0, 10.0, 10.0, 12.0]
    signal = await strategy.analyze(market_data(closes))
    assert isinstance(signal, Signal)
    assert signal.action == OrderSide.BUY


@pytest.mark.asyncio
async def test_analyze_bearish_crossover_returns_sell() -> None:
    """La corta cruza por debajo de la larga -> SELL."""
    strategy = make_strategy({"short_period": 2, "long_period": 3})
    closes = [12.0, 12.0, 12.0, 12.0, 12.0, 10.0]
    signal = await strategy.analyze(market_data(closes))
    assert isinstance(signal, Signal)
    assert signal.action == OrderSide.SELL


@pytest.mark.asyncio
async def test_get_required_params_returns_schema() -> None:
    """get_required_params devuelve el esquema esperado."""
    params = make_strategy().get_required_params()
    assert set(params) == {"short_period", "long_period", "quantity"}
    assert params["short_period"]["default"] == 10
    assert params["long_period"]["default"] == 20
    assert params["quantity"]["default"] == 0.1
