"""Adaptador real para la API de Hyperliquid usando HTTP.

NOTA: Esta es una implementación SIMPLIFICADA. La API real de Hyperliquid
requiere firmar cada orden con EIP-712 usando la private key de la wallet.
Aquí se envía el payload directamente a modo de esqueleto funcional; la
firma criptográfica y el manejo de WebSockets son trabajo futuro.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.core.entities.order import Order, OrderSide
from src.core.logging import get_logger
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter

logger = get_logger(__name__)


class HyperliquidRealAdapter(IHyperliquidAdapter):
    """Cliente HTTP real para la API de Hyperliquid.

    Args:
        base_url: URL base de la API (mainnet o testnet).
        api_key: API key / dirección de la wallet.
        secret: Secret / private key de la wallet.
        is_testnet: Si apunta al entorno de testnet.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        secret: str,
        is_testnet: bool = False,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.secret = secret
        self.is_testnet = is_testnet
        self._client: httpx.AsyncClient | None = None
        self._connected = False

    async def connect(self) -> None:
        """Crea el cliente HTTP y marca la conexión como activa."""
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self._connected = True
        logger.info(
            "hyperliquid_connected",
            base_url=self.base_url,
            is_testnet=self.is_testnet,
        )

    async def get_balance(self, asset: str = "USDC") -> float:
        """Consulta el balance disponible vía POST /info.

        Args:
            asset: Símbolo del activo (por defecto USDC).

        Returns:
            Balance del activo como float.

        Raises:
            RuntimeError: Si el cliente no está conectado.
        """
        client = self._require_client()
        payload = {"type": "clearinghouseState", "user": self.api_key}
        response = await client.post("/info", json=payload)
        response.raise_for_status()
        data = response.json()
        # Simplificado: en la API real se recorre assetPositions buscando el asset.
        return float(data.get("marginSummary", {}).get("accountValue", 0.0))

    async def get_ohlcv(
        self, symbol: str, interval: str = "1m", limit: int = 100
    ) -> list[dict]:
        """Obtiene velas históricas vía POST /info.

        Args:
            symbol: Símbolo del par (ej. "BTC-USD").
            interval: Marco temporal de cada vela.
            limit: Número de velas a solicitar.

        Returns:
            Lista de dicts con los datos OHLCV.

        Raises:
            RuntimeError: Si el cliente no está conectado.
        """
        client = self._require_client()
        payload = {"type": "candleSnapshot", "coin": symbol, "interval": interval}
        response = await client.post("/info", json=payload)
        response.raise_for_status()
        data = response.json()
        candles: list[dict] = data if isinstance(data, list) else []
        return candles[:limit]

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float | None = None,
        is_reduce_only: bool = False,
    ) -> Order:
        """Envía una orden vía POST /exchange.

        NOTA: La API real exige firmar el payload con EIP-712 usando la
        private key. Esta implementación envía el payload sin firmar como
        esqueleto funcional.

        Args:
            symbol: Símbolo del par.
            side: Lado de la orden (BUY/SELL).
            quantity: Cantidad a operar.
            price: Precio límite. None = orden de mercado.
            is_reduce_only: Si la orden solo reduce la posición.

        Returns:
            La orden creada.

        Raises:
            RuntimeError: Si el cliente no está conectado.
        """
        client = self._require_client()
        order_type = "limit" if price is not None else "market"
        payload: dict[str, Any] = {
            "action": {
                "type": "order",
                "orders": [
                    {
                        "coin": symbol,
                        "is_buy": side == OrderSide.BUY,
                        "sz": quantity,
                        "ord_type": order_type,
                        "reduce_only": is_reduce_only,
                    }
                ],
            },
            "nonce": 0,
        }
        if price is not None:
            payload["action"]["orders"][0]["limit_px"] = price

        response = await client.post("/exchange", json=payload)
        response.raise_for_status()
        logger.info(
            "hyperliquid_order_placed",
            symbol=symbol,
            side=side.value,
            quantity=quantity,
        )
        return Order(
            id=self._extract_order_id(response),
            bot_id="",
            symbol=symbol,
            side=side,
            price=price or 0.0,
            quantity=quantity,
        )

    async def close_position(self, symbol: str) -> Order:
        """Cierra la posición activa con una orden de mercado vía POST /exchange.

        Args:
            symbol: Símbolo del par a cerrar.

        Returns:
            La orden de cierre.

        Raises:
            RuntimeError: Si el cliente no está conectado.
        """
        client = self._require_client()
        payload = {
            "action": {
                "type": "order",
                "orders": [
                    {
                        "coin": symbol,
                        "is_buy": False,
                        "sz": 0.0,
                        "ord_type": "market",
                        "reduce_only": True,
                    }
                ],
            },
            "nonce": 0,
        }
        response = await client.post("/exchange", json=payload)
        response.raise_for_status()
        logger.info("hyperliquid_position_closed", symbol=symbol)
        return Order(
            id=self._extract_order_id(response),
            bot_id="",
            symbol=symbol,
            side=OrderSide.SELL,
            price=0.0,
            quantity=0.0,
        )

    async def subscribe_market_data(self, symbol: str, callback: Any) -> None:
        """Suscribe a datos en tiempo real.

        NOTA: El streaming por WebSocket es trabajo futuro.

        Raises:
            NotImplementedError: Siempre, ya que el WebSocket no está implementado.
        """
        raise NotImplementedError("WebSocket market data no implementado todavía")

    def _require_client(self) -> httpx.AsyncClient:
        """Devuelve el cliente HTTP o lanza error si no está conectado."""
        if self._client is None:
            raise RuntimeError("Adapter no conectado. Llama a connect() primero.")
        return self._client

    @staticmethod
    def _extract_order_id(response: httpx.Response) -> str:
        """Extrae el order id de la respuesta del exchange de forma defensiva."""
        statuses = response.json().get("response", {}).get("data", {}).get("statuses", [{}])
        return str(statuses[0].get("oid", ""))
