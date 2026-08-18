"""StrategyExecutor: bucle de ejecución que conecta estrategias con adapters.

Cada executor corre una estrategia contra un adapter de Hyperliquid en un
bucle periódico: obtiene velas, las convierte a ``market_data``, pide una
señal a la estrategia y, si hay acción (BUY/SELL), ejecuta la orden.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.core.entities.bot import Bot
from src.core.entities.order import Order, OrderSide
from src.core.logging import get_logger
from src.core.models import Trade
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.ports.i_strategy import IStrategy
from src.core.services.event_bus import EVENT_BOT_TRADE_EXECUTED, get_event_bus
from src.core.services.risk_manager import RiskManager

logger = get_logger(__name__)

# Fracción del balance que se usa por defecto cuando la señal no trae cantidad.
_DEFAULT_BALANCE_FRACTION = 0.1


class StrategyExecutor:
    """Ejecuta una estrategia contra un adapter en un bucle periódico.

    Args:
        bot: Entidad del bot que se está ejecutando.
        adapter: Adapter de Hyperliquid (real o paper) sobre el que operar.
        strategy: Instancia de la estrategia a ejecutar.
        risk_manager: RiskManager opcional que valida las órdenes antes de
            ejecutarlas. Si es None, no se aplica validación de riesgo.
    """

    def __init__(
        self,
        bot: Bot,
        adapter: IHyperliquidAdapter,
        strategy: IStrategy,
        risk_manager: RiskManager | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.bot = bot
        self.adapter = adapter
        self.strategy = strategy
        self.risk_manager = risk_manager
        self._session_factory = session_factory
        self.trades: list[Order] = []
        self._running = False

    @property
    def is_running(self) -> bool:
        """Indica si el bucle ``run_forever`` está activo."""
        return self._running

    async def run_once(self) -> None:
        """Ejecuta una única iteración del ciclo de trading.

        1. Obtiene velas OHLCV del símbolo del bot.
        2. Las convierte a ``market_data`` (última vela + historial).
        3. Pide una señal a la estrategia.
        4. Si la señal es BUY/SELL, calcula la cantidad y coloca la orden.
        5. Si hay RiskManager, valida la orden antes de ejecutarla y registra
           el trade tras un fill.
        """
        candles = await self.adapter.get_ohlcv(
            self.bot.symbol, interval="1m", limit=100
        )
        if not candles:
            logger.warning(
                "strategy_executor.no_candles",
                bot_id=self.bot.id,
                symbol=self.bot.symbol,
            )
            return

        market_data = self._build_market_data(candles)
        signal = await self.strategy.analyze(market_data)

        if signal is None or signal.action not in (OrderSide.BUY, OrderSide.SELL):
            return

        current_price = float(candles[-1]["close"])
        quantity = signal.quantity
        if quantity is None:
            quantity = await self._default_quantity(current_price)

        if self.risk_manager is not None:
            ok, reason = await self.risk_manager.validate_order(
                self.bot.symbol, signal.action, quantity, current_price
            )
            if not ok:
                logger.warning(
                    "strategy_executor.order_rejected",
                    bot_id=self.bot.id,
                    symbol=self.bot.symbol,
                    side=signal.action.value,
                    quantity=quantity,
                    price=current_price,
                    reason=reason,
                )
                return

        order = await self.adapter.place_order(
            self.bot.symbol, signal.action, quantity
        )
        self.trades.append(order)
        await self._persist_trade(order)

        get_event_bus().publish(
            EVENT_BOT_TRADE_EXECUTED,
            {
                "user_id": int(self.bot.user_id),
                "bot_id": int(self.bot.id),
                "trade": {
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "price": order.price,
                    "qty": order.quantity,
                    "pnl": 0.0,
                },
            },
        )

        if self.risk_manager is not None:
            await self.risk_manager.record_trade(order)

        logger.info(
            "strategy_executor.trade",
            bot_id=self.bot.id,
            symbol=self.bot.symbol,
            order_id=order.id,
            side=signal.action.value,
            quantity=quantity,
            price=order.price,
        )

    async def run_forever(self, interval_seconds: int = 60) -> None:
        """Bucle infinito que ejecuta ``run_once`` cada ``interval_seconds``.

        Los errores de una iteración se registran y no detienen el bucle.
        Se detiene de forma limpia cuando se llama a :meth:`stop`.
        """
        self._running = True
        while self._running:
            try:
                await self.run_once()
            except Exception:
                logger.exception(
                    "strategy_executor.iteration_failed",
                    bot_id=self.bot.id,
                    symbol=self.bot.symbol,
                )
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        """Detiene el bucle ``run_forever`` de forma cooperativa."""
        self._running = False

    async def _persist_trade(self, order: Order) -> None:
        """Persiste el trade ejecutado en la base de datos.

        Si no se configuró un ``session_factory`` (p. ej. en tests unitarios),
        el trade solo se mantiene en memoria y no se persiste.
        """
        if self._session_factory is None:
            return
        try:
            async with self._session_factory() as session:
                trade = Trade(
                    bot_id=int(self.bot.id),
                    user_id=int(self.bot.user_id),
                    symbol=order.symbol,
                    side=order.side.value,
                    price=order.price,
                    quantity=order.quantity,
                    pnl=0.0,
                )
                session.add(trade)
                await session.commit()
        except Exception:
            logger.exception(
                "strategy_executor.persist_trade_failed",
                bot_id=self.bot.id,
                symbol=self.bot.symbol,
            )

    async def _default_quantity(self, current_price: float) -> float:
        """Calcula la cantidad por defecto: 10% del balance / precio actual."""
        balance = await self.adapter.get_balance()
        return (balance * _DEFAULT_BALANCE_FRACTION) / current_price

    @staticmethod
    def _build_market_data(candles: list[dict[str, Any]]) -> dict[str, Any]:
        """Convierte las velas crudas en el dict ``market_data`` de la estrategia."""
        return {
            "last": candles[-1],
            "history": candles,
            "closes": [float(c["close"]) for c in candles],
        }
