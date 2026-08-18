"""RiskManager: valida órdenes contra límites de riesgo antes de ejecutarlas.

Protege a los bots de pérdidas excesivas comprobando cada orden contra una
serie de límites configurables (tamaño de posición, pérdida diaria, drawdown,
número de posiciones abiertas y stop loss) antes de que llegue al exchange.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from src.core.entities.bot import Bot
from src.core.entities.order import Order, OrderSide
from src.core.logging import get_logger
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.event_bus import (
    EVENT_BOT_RISK_HALTED,
    EVENT_BOT_RISK_UPDATED,
    get_event_bus,
)

logger = get_logger(__name__)


@dataclass
class RiskConfig:
    """Límites de riesgo configurables para un bot.

    Attributes:
        max_position_size_pct: Máximo % del balance por posición (0-1).
        max_daily_loss_pct: Máxima pérdida diaria como % del balance inicial (0-1).
        max_drawdown_pct: Máximo drawdown desde el balance pico (0-1).
        max_open_positions: Número máximo de posiciones abiertas simultáneas.
        stop_loss_pct: Stop loss opcional por posición (0-1). None = desactivado.
    """

    max_position_size_pct: float = 0.25
    max_daily_loss_pct: float = 0.05
    max_drawdown_pct: float = 0.15
    max_open_positions: int = 3
    stop_loss_pct: float | None = None


class RiskManager:
    """Valida órdenes contra los límites de riesgo del bot.

    Mantiene el estado interno (balance inicial, balance pico, P&L diario y
    posiciones abiertas) para decidir si una orden puede ejecutarse.

    Args:
        bot: Entidad del bot cuyo riesgo se gestiona.
        adapter: Adapter de Hyperliquid (real o paper) para consultar el balance.
    """

    def __init__(self, bot: Bot, adapter: IHyperliquidAdapter) -> None:
        self.bot = bot
        self.adapter = adapter
        self.config = self._config_from_bot(bot)
        self._starting_balance: float = 0.0
        self._peak_balance: float = 0.0
        self._daily_pnl: float = 0.0
        self._positions: dict[str, dict[str, Any]] = {}
        self._halted: bool = False
        self._halt_reason: str | None = None

    @staticmethod
    def _config_from_bot(bot: Bot) -> RiskConfig:
        """Construye el RiskConfig a partir de ``bot.config["risk_config"]``.

        Solo se toman los campos conocidos del RiskConfig; el resto se ignora.
        """
        raw = bot.config.get("risk_config", {})
        if not isinstance(raw, dict):
            return RiskConfig()
        valid = {k: v for k, v in raw.items() if k in {f.name for f in fields(RiskConfig)}}
        return RiskConfig(**valid)

    async def _load_balance(self) -> float:
        """Carga el balance inicial/pico la primera vez y devuelve el balance actual."""
        if self._starting_balance == 0.0:
            self._starting_balance = await self.adapter.get_balance()
            self._peak_balance = self._starting_balance
        return await self.adapter.get_balance()

    async def validate_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
    ) -> tuple[bool, str]:
        """Valida una orden contra los límites de riesgo.

        Args:
            symbol: Símbolo del par (ej. "BTC-USD").
            side: Lado de la orden (BUY/SELL).
            quantity: Cantidad a operar.
            price: Precio de referencia de la orden.

        Returns:
            ``(True, "OK")`` si la orden pasa todos los controles, o
            ``(False, reason)`` con el motivo del rechazo.
        """
        if self._halted:
            return False, self._halt_reason or "Trading halted"

        balance = await self._load_balance()

        # 1. Tamaño de posición: quantity * price <= balance * max_position_size_pct
        if quantity * price > balance * self.config.max_position_size_pct:
            return False, "Position size exceeds max_position_size_pct"

        # 2. Pérdida diaria: si la pérdida realizada hoy supera el límite, rechazar
        daily_loss_limit = self.config.max_daily_loss_pct * self._starting_balance
        if self._daily_pnl < 0 and abs(self._daily_pnl) > daily_loss_limit:
            return False, "Daily loss limit exceeded"

        # 3. Drawdown: si la caída desde el balance pico supera el límite, rechazar
        if self._peak_balance > 0:
            drawdown = (self._peak_balance - balance) / self._peak_balance
            if drawdown > self.config.max_drawdown_pct:
                return False, "Max drawdown exceeded"

        # 4. Posiciones abiertas: rechazar si ya hay el máximo permitido
        if len(self._positions) >= self.config.max_open_positions:
            return False, "Max open positions reached"

        # 5. Stop loss: si la posición del símbolo supera el stop loss, rechazar
        if self.config.stop_loss_pct is not None and side == OrderSide.BUY:
            position = self._positions.get(symbol)
            if position is not None and position["side"] == OrderSide.BUY:
                entry = float(position["entry_price"])
                if entry > 0 and (entry - price) / entry > self.config.stop_loss_pct:
                    return False, "Stop loss triggered for symbol"

        return True, "OK"

    async def record_trade(self, order: Order) -> None:
        """Actualiza el estado interno tras una orden ejecutada.

        Registra el P&L realizado en ventas, actualiza las posiciones abiertas
        y el balance pico.

        Args:
            order: Orden ya ejecutada (FILLED).
        """
        if order.side == OrderSide.BUY:
            position = self._positions.get(order.symbol)
            if position is None:
                self._positions[order.symbol] = {
                    "side": OrderSide.BUY,
                    "quantity": order.quantity,
                    "entry_price": order.price,
                }
            else:
                total_qty = float(position["quantity"]) + order.quantity
                position["entry_price"] = (
                    float(position["entry_price"]) * float(position["quantity"])
                    + order.price * order.quantity
                ) / total_qty
                position["quantity"] = total_qty
        else:  # SELL
            position = self._positions.get(order.symbol)
            if position is not None:
                realized = (order.price - float(position["entry_price"])) * order.quantity
                self._daily_pnl += realized
                position["quantity"] = float(position["quantity"]) - order.quantity
                if float(position["quantity"]) <= 0:
                    self._positions.pop(order.symbol, None)

        balance = await self.adapter.get_balance()
        if balance > self._peak_balance:
            self._peak_balance = balance

        status = await self.status()
        get_event_bus().publish(
            EVENT_BOT_RISK_UPDATED,
            {
                "user_id": int(self.bot.user_id),
                "bot_id": int(self.bot.id),
                "status": status,
            },
        )

    def halt(self, reason: str | None = None) -> None:
        """Detiene manualmente el trading del bot.

        Args:
            reason: Motivo opcional del halt.
        """
        self._halted = True
        self._halt_reason = reason or "Manually halted"
        get_event_bus().publish(
            EVENT_BOT_RISK_HALTED,
            {
                "user_id": int(self.bot.user_id),
                "bot_id": int(self.bot.id),
                "reason": self._halt_reason,
            },
        )
        logger.warning("risk_manager.halted", bot_id=self.bot.id, reason=self._halt_reason)

    def resume(self) -> None:
        """Reanuda el trading del bot tras un halt."""
        self._halted = False
        self._halt_reason = None
        logger.info("risk_manager.resumed", bot_id=self.bot.id)

    async def status(self) -> dict[str, Any]:
        """Devuelve el estado actual del risk manager.

        Returns:
            Dict con balance inicial/actual/pico, P&L diario, drawdown,
            posiciones abiertas y estado de halt.
        """
        balance = await self._load_balance()
        drawdown_pct = 0.0
        if self._peak_balance > 0:
            drawdown_pct = (self._peak_balance - balance) / self._peak_balance
        return {
            "bot_id": int(self.bot.id),
            "starting_balance": self._starting_balance,
            "current_balance": balance,
            "peak_balance": self._peak_balance,
            "daily_pnl": self._daily_pnl,
            "drawdown_pct": drawdown_pct,
            "open_positions": len(self._positions),
            "is_halted": self._halted,
            "halt_reason": self._halt_reason,
        }


# Caché global de RiskManager por bot (acceso singleton).
_risk_managers: dict[str, RiskManager] = {}


def get_risk_manager(bot: Bot, adapter: IHyperliquidAdapter) -> RiskManager:
    """Devuelve el RiskManager singleton para el bot, creándolo si no existe.

    Args:
        bot: Entidad del bot.
        adapter: Adapter de Hyperliquid del bot.

    Returns:
        El RiskManager asociado al bot.
    """
    key = str(bot.id)
    if key not in _risk_managers:
        _risk_managers[key] = RiskManager(bot, adapter)
    return _risk_managers[key]


def clear_risk_manager(bot_id: int) -> None:
    """Elimina el RiskManager del bot del caché global (al detener el bot).

    Args:
        bot_id: Identificador del bot.
    """
    _risk_managers.pop(str(bot_id), None)
