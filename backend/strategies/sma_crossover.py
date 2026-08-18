"""Estrategia de ejemplo: cruce de medias móviles simples (SMA).

Compra cuando la SMA corta cruza por encima de la larga y vende cuando cruza
por debajo. Solo para validar el flujo de ejecución; no usar en producción.
"""

from __future__ import annotations

from typing import Any

from base_strategy import BaseStrategy
from src.core.entities.order import OrderSide
from src.core.ports.i_strategy import Signal


class SmaCrossoverStrategy(BaseStrategy):
    """Compra/vende según el cruce de una SMA corta sobre una larga.

    Config:
        short_period: Periodo de la SMA corta (default 10).
        long_period: Periodo de la SMA larga (default 20).
        quantity: Cantidad fija a operar (default 0.1).
    """

    name = "sma_crossover"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.short_period: int = int(config.get("short_period", 10))
        self.long_period: int = int(config.get("long_period", 20))
        self.quantity: float = float(config.get("quantity", 0.1))
        self._prev_short: float | None = None
        self._prev_long: float | None = None

    async def analyze(self, market_data: dict[str, Any]) -> Signal | None:
        """Detecta el cruce de SMAs y devuelve una señal BUY/SELL o None.

        Args:
            market_data: Dict con la clave ``closes`` (lista de cierres).

        Returns:
            Señal BUY si la corta cruza por encima, SELL si cruza por debajo,
            o None si no hay cruce o faltan datos.
        """
        closes: list[float] = market_data.get("closes", [])
        if len(closes) < max(self.short_period, self.long_period) + 1:
            return None

        short_now = sum(closes[-self.short_period :]) / self.short_period
        long_now = sum(closes[-self.long_period :]) / self.long_period
        prev_short = (
            sum(closes[-(self.short_period + 1) : -1]) / self.short_period
            if self._prev_short is None
            else self._prev_short
        )
        prev_long = (
            sum(closes[-(self.long_period + 1) : -1]) / self.long_period
            if self._prev_long is None
            else self._prev_long
        )

        self._prev_short = short_now
        self._prev_long = long_now

        if prev_short <= prev_long and short_now > long_now:
            return Signal(action=OrderSide.BUY, quantity=self.quantity, confidence=0.7)
        if prev_short >= prev_long and short_now < long_now:
            return Signal(action=OrderSide.SELL, quantity=self.quantity, confidence=0.7)
        return None

    def get_required_params(self) -> dict[str, Any]:
        """Devuelve el esquema de parámetros para la UI."""
        return {
            "short_period": {"type": "int", "default": 10, "min": 2, "max": 200},
            "long_period": {"type": "int", "default": 20, "min": 2, "max": 400},
            "quantity": {"type": "float", "default": 0.1, "min": 0.0},
        }
