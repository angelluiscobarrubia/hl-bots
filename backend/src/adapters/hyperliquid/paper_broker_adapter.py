"""Adaptador Paper Broker que simula Hyperliquid sin dinero real.

Mantiene todo el estado en memoria (balance, posiciones, historial de órdenes)
y genera datos de mercado sintéticos deterministas para que los tests sean
reproducibles. No realiza ninguna llamada de red.
"""

from __future__ import annotations

import random
import uuid
import zlib
from typing import Any

from src.core.entities.order import Order, OrderSide, OrderStatus
from src.core.logging import get_logger
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter

logger = get_logger(__name__)


class PaperBrokerAdapter(IHyperliquidAdapter):
    """Simula el exchange Hyperliquid en memoria (modo paper trading).

    Args:
        initial_balance: Balance inicial en USDC.
        bot_id: Identificador del bot propietario de las órdenes.
    """

    def __init__(self, initial_balance: float = 10000.0, bot_id: str = "paper-broker") -> None:
        self._initial_balance = initial_balance
        self._bot_id = bot_id
        self._balance = initial_balance
        self._connected = False
        self._positions: dict[str, dict[str, Any]] = {}
        self._order_history: list[Order] = []
        self._callbacks: dict[str, Any] = {}

    async def connect(self) -> None:
        """Inicializa la conexión. No-op en paper mode."""
        self._connected = True
        logger.info("paper_broker_connected", bot_id=self._bot_id)

    async def get_balance(self, asset: str = "USDC") -> float:
        """Devuelve el balance disponible en el activo indicado.

        Args:
            asset: Símbolo del activo (por defecto USDC).

        Returns:
            Balance actual en el activo.
        """
        return self._balance

    async def get_ohlcv(self, symbol: str, interval: str = "1m", limit: int = 100) -> list[dict]:
        """Genera velas sintéticas deterministas basadas en el hash del símbolo.

        Args:
            symbol: Símbolo del par (ej. "BTC-USD").
            interval: Marco temporal de cada vela (ej. "1m", "1h").
            limit: Número de velas a generar.

        Returns:
            Lista de dicts con claves open/high/low/close/volume.
        """
        candles = [self._synthetic_candle(symbol, i) for i in range(limit)]
        logger.debug(
            "paper_ohlcv_generated",
            symbol=symbol,
            interval=interval,
            count=len(candles),
        )
        return candles

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float | None = None,
        is_reduce_only: bool = False,
    ) -> Order:
        """Crea una orden y la llena inmediatamente (paper mode).

        Args:
            symbol: Símbolo del par.
            side: Lado de la orden (BUY/SELL).
            quantity: Cantidad a operar.
            price: Precio límite. Si es None, usa el precio de mercado.
            is_reduce_only: Si la orden solo reduce la posición.

        Returns:
            La orden con estado FILLED.
        """
        fill_price = price if price is not None else await self._market_price(symbol)

        order = Order(
            id=str(uuid.uuid4()),
            bot_id=self._bot_id,
            symbol=symbol,
            side=side,
            price=fill_price,
            quantity=quantity,
            status=OrderStatus.FILLED,
        )

        self._apply_fill(symbol, side, quantity, fill_price)
        self._order_history.append(order)

        logger.info(
            "paper_order_filled",
            order_id=order.id,
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            price=fill_price,
        )
        return order

    async def close_position(self, symbol: str) -> Order:
        """Cierra la posición activa para un símbolo con una orden opuesta.

        Args:
            symbol: Símbolo del par a cerrar.

        Returns:
            La orden de cierre con estado FILLED.

        Raises:
            ValueError: Si no hay posición abierta para el símbolo.
        """
        position = self._positions.get(symbol)
        if position is None:
            raise ValueError(f"No hay posición abierta para {symbol}")

        close_side = OrderSide.SELL if position["side"] == OrderSide.BUY else OrderSide.BUY
        quantity = float(position["quantity"])
        fill_price = await self._market_price(symbol)

        order = Order(
            id=str(uuid.uuid4()),
            bot_id=self._bot_id,
            symbol=symbol,
            side=close_side,
            price=fill_price,
            quantity=quantity,
            status=OrderStatus.FILLED,
        )

        self._apply_fill(symbol, close_side, quantity, fill_price)
        self._positions.pop(symbol, None)
        self._order_history.append(order)

        logger.info(
            "paper_position_closed",
            order_id=order.id,
            symbol=symbol,
            side=close_side.value,
            quantity=quantity,
        )
        return order

    async def subscribe_market_data(self, symbol: str, callback: Any) -> None:
        """Almacena el callback de market data. No hay WebSocket real en paper.

        Args:
            symbol: Símbolo a suscribir.
            callback: Callable a invocar con los datos de mercado.
        """
        self._callbacks[symbol] = callback
        logger.debug("paper_subscribed", symbol=symbol)

    def _apply_fill(self, symbol: str, side: OrderSide, quantity: float, price: float) -> None:
        """Actualiza balance y posición tras un fill."""
        cost = quantity * price
        if side == OrderSide.BUY:
            self._balance -= cost
            position = self._positions.setdefault(
                symbol, {"side": OrderSide.BUY, "quantity": 0.0, "entry_price": price}
            )
            position["quantity"] = float(position["quantity"]) + quantity
            position["entry_price"] = price
        else:
            self._balance += cost
            position = self._positions.get(symbol)
            if position is not None:
                position["quantity"] = float(position["quantity"]) - quantity
                if float(position["quantity"]) <= 0:
                    self._positions.pop(symbol, None)

    async def _market_price(self, symbol: str) -> float:
        """Devuelve el precio de la última vela sintética (precio de mercado)."""
        candles = await self.get_ohlcv(symbol, interval="1m", limit=1)
        return float(candles[-1]["close"])

    @staticmethod
    def _synthetic_candle(symbol: str, index: int) -> dict[str, float]:
        """Genera una vela determinista a partir del símbolo e índice."""
        seed = zlib.crc32(f"{symbol}:{index}".encode())
        rng = random.Random(seed)  # noqa: S311 - datos sintéticos, no criptografía
        base = 100.0 + (seed % 10000) / 100.0
        open_price = base + rng.uniform(-5, 5)
        close = open_price + rng.uniform(-3, 3)
        high = max(open_price, close) + rng.uniform(0, 2)
        low = min(open_price, close) - rng.uniform(0, 2)
        volume = rng.uniform(1, 100)
        return {
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": round(volume, 2),
        }
