"""Estrategia de ejemplo: cruce de medias móviles simples.

Solo para validar el flujo de carga dinámica. No usar en producción.
"""

from __future__ import annotations

from typing import Any

from base_strategy import BaseStrategy
from src.core.entities.order import OrderSide
from src.core.ports.i_strategy import Signal


class MovingAverageCrossover(BaseStrategy):
    """Compra cuando la SMA rápida cruza por encima de la lenta."""

    name = "moving_average_crossover"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.fast_period: int = int(config.get("fast_period", 9))
        self.slow_period: int = int(config.get("slow_period", 21))
        self.quantity: float = float(config.get("quantity", 0.01))
        self._prev_fast: float | None = None
        self._prev_slow: float | None = None

    async def analyze(self, market_data: dict[str, Any]) -> Signal | None:
        closes: list[float] = market_data.get("closes", [])
        if len(closes) < max(self.fast_period, self.slow_period) + 1:
            return None

        fast_now = sum(closes[-self.fast_period :]) / self.fast_period
        slow_now = sum(closes[-self.slow_period :]) / self.slow_period
        prev_fast = (
            sum(closes[-(self.fast_period + 1) : -1]) / self.fast_period
            if self._prev_fast is None
            else self._prev_fast
        )
        prev_slow = (
            sum(closes[-(self.slow_period + 1) : -1]) / self.slow_period
            if self._prev_slow is None
            else self._prev_slow
        )

        self._prev_fast = fast_now
        self._prev_slow = slow_now

        if prev_fast <= prev_slow and fast_now > slow_now:
            return Signal(action=OrderSide.BUY, quantity=self.quantity, confidence=0.7)
        if prev_fast >= prev_slow and fast_now < slow_now:
            return Signal(action=OrderSide.SELL, quantity=self.quantity, confidence=0.7)
        return None

    def get_required_params(self) -> dict[str, Any]:
        return {
            "fast_period": {"type": "int", "default": 9, "min": 2, "max": 200},
            "slow_period": {"type": "int", "default": 21, "min": 2, "max": 400},
            "quantity": {"type": "float", "default": 0.01, "min": 0.0},
        }
