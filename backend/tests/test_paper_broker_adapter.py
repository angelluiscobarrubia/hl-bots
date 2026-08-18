"""Tests para el adaptador PaperBrokerAdapter (paper trading)."""

import pytest
from src.adapters.hyperliquid.paper_broker_adapter import PaperBrokerAdapter
from src.core.entities.order import OrderSide, OrderStatus


@pytest.fixture
async def adapter() -> PaperBrokerAdapter:
    """Fixture que provee un PaperBrokerAdapter conectado."""
    a = PaperBrokerAdapter()
    await a.connect()
    return a


@pytest.mark.asyncio
async def test_connect_sets_connected(adapter: PaperBrokerAdapter) -> None:
    """Después de connect(), el estado interno está conectado."""
    assert adapter._connected is True


@pytest.mark.asyncio
async def test_initial_balance() -> None:
    """El balance inicial por defecto es 10000.0."""
    adapter = PaperBrokerAdapter()
    assert adapter._balance == 10000.0


@pytest.mark.asyncio
async def test_get_balance_returns_initial(adapter: PaperBrokerAdapter) -> None:
    """Antes de operar, el balance es igual al inicial."""
    balance = await adapter.get_balance()
    assert balance == 10000.0


@pytest.mark.asyncio
async def test_place_buy_order_fills_immediately(adapter: PaperBrokerAdapter) -> None:
    """Una orden de compra se llena de inmediato y reduce el balance."""
    order = await adapter.place_order("BTC-USD", OrderSide.BUY, quantity=1.0, price=100.0)
    assert order.status == OrderStatus.FILLED
    assert await adapter.get_balance() == 10000.0 - 100.0


@pytest.mark.asyncio
async def test_place_sell_order_fills_immediately(adapter: PaperBrokerAdapter) -> None:
    """Una orden de venta se llena de inmediato y aumenta el balance (si hay posición)."""
    await adapter.place_order("BTC-USD", OrderSide.BUY, quantity=1.0, price=100.0)
    order = await adapter.place_order("BTC-USD", OrderSide.SELL, quantity=1.0, price=150.0)
    assert order.status == OrderStatus.FILLED
    assert await adapter.get_balance() == 10000.0 - 100.0 + 150.0


@pytest.mark.asyncio
async def test_place_market_order_uses_last_price(adapter: PaperBrokerAdapter) -> None:
    """Una orden de mercado (price=None) usa el cierre de la última vela."""
    candles = await adapter.get_ohlcv("BTC-USD", interval="1m", limit=1)
    last_close = candles[-1]["close"]
    order = await adapter.place_order("BTC-USD", OrderSide.BUY, quantity=1.0, price=None)
    assert order.status == OrderStatus.FILLED
    assert order.price == last_close


@pytest.mark.asyncio
async def test_close_position_closes_open_position(adapter: PaperBrokerAdapter) -> None:
    """Tras una compra, close_position crea una orden opuesta y cierra la posición."""
    await adapter.place_order("BTC-USD", OrderSide.BUY, quantity=2.0, price=100.0)
    assert "BTC-USD" in adapter._positions

    close_order = await adapter.close_position("BTC-USD")
    assert close_order.side == OrderSide.SELL
    assert close_order.status == OrderStatus.FILLED
    assert "BTC-USD" not in adapter._positions


@pytest.mark.asyncio
async def test_get_ohlcv_returns_synthetic_data(adapter: PaperBrokerAdapter) -> None:
    """get_ohlcv devuelve una lista de dicts con claves OHLCV."""
    candles = await adapter.get_ohlcv("BTC-USD", interval="1m", limit=10)
    assert len(candles) == 10
    for candle in candles:
        assert {"open", "high", "low", "close", "volume"} <= set(candle)


@pytest.mark.asyncio
async def test_subscribe_market_data_stores_callback(adapter: PaperBrokerAdapter) -> None:
    """El callback se almacena sin errores."""
    def callback(data: dict) -> None:
        pass

    await adapter.subscribe_market_data("BTC-USD", callback)
    assert "BTC-USD" in adapter._callbacks
    assert adapter._callbacks["BTC-USD"] is callback
