from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel
from src.core.entities.order import OrderSide


class Signal(BaseModel):
    action: OrderSide  # BUY, SELL, o podríamos agregar HOLD
    quantity: float | None = None  # Si es None, usa la cantidad por defecto configurada
    confidence: float = 1.0  # 0 a 1 para futuros filtros


class IStrategy(ABC):
    """Interfaz que deben implementar todas las estrategias."""

    @abstractmethod
    def __init__(self, config: dict[str, Any]) -> None:
        """Recibe la configuración específica de la instancia del bot."""
        pass

    @abstractmethod
    async def analyze(self, market_data: dict[str, Any]) -> Signal | None:
        """
        Analiza los datos de mercado (velas, orderbook, trades) y devuelve
        una señal de acción (BUY/SELL) o None si no hay acción.
        """
        pass

    @abstractmethod
    def get_required_params(self) -> dict[str, Any]:
        """Devuelve el esquema de parámetros que necesita la UI para configurar esta estrategia."""
        pass
