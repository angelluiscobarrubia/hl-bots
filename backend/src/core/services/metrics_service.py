"""MetricsService: agrega métricas de rendimiento de los trades de un bot.

Consulta los trades persistidos en la base de datos y calcula métricas
agregadas (win rate, P&L total, Sharpe ratio, curva de equity, etc.) para
alimentar el dashboard de métricas del frontend.
"""

from __future__ import annotations

import statistics
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.core.logging import get_logger
from src.core.models import Trade

logger = get_logger(__name__)


class MetricsService:
    """Agrega métricas de rendimiento a partir de los trades persistidos."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_bot_metrics(self, bot_id: int, user_id: int) -> dict[str, Any]:
        """Devuelve las métricas agregadas de un bot.

        Args:
            bot_id: Identificador del bot.
            user_id: Identificador del usuario dueño (filtro de seguridad).

        Returns:
            Dict con totales, win rate, P&L, Sharpe ratio y balances.
        """
        trades = await self._list_trades(bot_id, user_id)

        total = len(trades)
        winning = sum(1 for t in trades if t.pnl > 0)
        losing = sum(1 for t in trades if t.pnl < 0)
        total_pnl = sum(t.pnl for t in trades)
        avg_pnl = total_pnl / total if total else 0.0
        max_win = max((t.pnl for t in trades), default=0.0)
        max_loss = min((t.pnl for t in trades), default=0.0)

        sharpe_ratio: float | None = None
        if total > 1:
            std = statistics.stdev([t.pnl for t in trades])
            if std > 0:
                sharpe_ratio = statistics.mean([t.pnl for t in trades]) / std

        return {
            "bot_id": bot_id,
            "total_trades": total,
            "winning_trades": winning,
            "losing_trades": losing,
            "win_rate": winning / total if total else 0.0,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "max_win": max_win,
            "max_loss": max_loss,
            "sharpe_ratio": sharpe_ratio,
            "starting_balance": 0.0,
            "current_balance": total_pnl,
        }

    async def get_bot_trades(
        self,
        bot_id: int,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Devuelve los trades de un bot paginados, del más reciente al más antiguo.

        Args:
            bot_id: Identificador del bot.
            user_id: Identificador del usuario dueño.
            limit: Número máximo de trades a devolver.
            offset: Desplazamiento para paginación.

        Returns:
            Lista de dicts con los datos de cada trade.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(Trade)
                .where(Trade.bot_id == bot_id, Trade.user_id == user_id)
                .order_by(Trade.executed_at.desc())
                .limit(limit)
                .offset(offset)
            )
            trades = result.scalars().all()
        return [self._trade_to_dict(t) for t in trades]

    async def get_equity_curve(self, bot_id: int, user_id: int) -> list[dict[str, Any]]:
        """Devuelve la curva de equity (P&L acumulado) de un bot a lo largo del tiempo.

        La curva empieza en 0 y acumula el P&L de cada trade en orden cronológico.

        Args:
            bot_id: Identificador del bot.
            user_id: Identificador del usuario dueño.

        Returns:
            Lista de puntos ``{"timestamp": ..., "equity": ...}``.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(Trade)
                .where(Trade.bot_id == bot_id, Trade.user_id == user_id)
                .order_by(Trade.executed_at.asc())
            )
            trades = result.scalars().all()

        cumulative = 0.0
        points: list[dict[str, Any]] = []
        for t in trades:
            cumulative += t.pnl
            points.append({"timestamp": t.executed_at, "equity": cumulative})
        return points

    async def _list_trades(self, bot_id: int, user_id: int) -> list[Trade]:
        """Devuelve todos los trades de un bot (sin paginar)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Trade).where(Trade.bot_id == bot_id, Trade.user_id == user_id)
            )
            return list(result.scalars().all())

    @staticmethod
    def _trade_to_dict(trade: Trade) -> dict[str, Any]:
        """Convierte un modelo Trade a dict para serialización."""
        return {
            "id": trade.id,
            "bot_id": trade.bot_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "price": trade.price,
            "quantity": trade.quantity,
            "pnl": trade.pnl,
            "executed_at": trade.executed_at,
        }


# Singleton lazy: no falla al importar si la DB no está configurada.
_metrics_service_instance: MetricsService | None = None


def get_metrics_service() -> MetricsService:
    """Devuelve el singleton del MetricsService, creándolo lazily."""
    global _metrics_service_instance
    if _metrics_service_instance is None:
        from src.adapters.database.session import async_session_factory

        _metrics_service_instance = MetricsService(session_factory=async_session_factory)
    return _metrics_service_instance


def clear_metrics_service() -> None:
    """Resetea el singleton del MetricsService (principalmente para tests)."""
    global _metrics_service_instance
    _metrics_service_instance = None
