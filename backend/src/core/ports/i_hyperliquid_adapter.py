from abc import ABC, abstractmethod
from typing import Any

from src.core.entities.order import Order, OrderSide


class IHyperliquidAdapter(ABC):
    """Puerto para conectar con Hyperliquid (Real o Paper)"""

    @abstractmethod
    async def connect(self) -> None:
        """Inicializa la conexión (WebSockets / HTTP)"""
        pass

    @abstractmethod
    async def get_balance(self, asset: str = "USDC") -> float:
        """Obtiene el balance disponible"""
        pass

    @abstractmethod
    async def get_ohlcv(self, symbol: str, interval: str = "1m", limit: int = 100) -> list[dict]:
        """Obtiene velas para análisis técnico"""
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float | None = None,  # None = Market Order
        is_reduce_only: bool = False,
    ) -> Order:
        """Ejecuta una orden en el exchange o en Paper"""
        pass

    @abstractmethod
    async def close_position(self, symbol: str) -> Order:
        """Cierra la posición activa para un símbolo"""
        pass

    @abstractmethod
    async def subscribe_market_data(self, symbol: str, callback: Any) -> None:
        """Suscribe a datos en tiempo real (WebSocket)"""
        pass
