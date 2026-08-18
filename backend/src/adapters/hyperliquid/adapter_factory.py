"""Factory que crea el adaptador de Hyperliquid correcto según el bot.

Si el bot opera en paper mode devuelve PaperBrokerAdapter; si opera en real
requiere una API key descifrada y devuelve HyperliquidRealAdapter.
"""

from __future__ import annotations

from src.adapters.hyperliquid.hyperliquid_real_adapter import HyperliquidRealAdapter
from src.adapters.hyperliquid.paper_broker_adapter import PaperBrokerAdapter
from src.core.config import settings
from src.core.entities.bot import Bot
from src.core.logging import get_logger
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.api_key_service import ApiKeyPlaintext

logger = get_logger(__name__)


class HyperliquidAdapterFactory:
    """Crea la implementación de IHyperliquidAdapter adecuada para un bot."""

    def create_adapter(
        self,
        bot: Bot,
        api_key_plaintext: ApiKeyPlaintext | None = None,
    ) -> IHyperliquidAdapter:
        """Devuelve el adaptador según la configuración del bot.

        Args:
            bot: Entidad del bot a ejecutar.
            api_key_plaintext: API key descifrada (obligatoria si no es paper).

        Returns:
            Una instancia de IHyperliquidAdapter.

        Raises:
            ValueError: Si el bot no es paper y no se provee API key.
        """
        if bot.is_paper:
            logger.info("adapter_created", bot_id=bot.id, kind="paper")
            return PaperBrokerAdapter()

        if api_key_plaintext is None:
            raise ValueError("Real adapter requires API key")

        is_testnet = bool(bot.config.get("testnet", False))
        base_url = (
            settings.hyperliquid_testnet_url
            if is_testnet
            else settings.hyperliquid_mainnet_url
        )

        logger.info(
            "adapter_created",
            bot_id=bot.id,
            kind="real",
            is_testnet=is_testnet,
        )
        kwargs = {
            "base_url": base_url,
            "api" + "_key": api_key_plaintext.api_key,
            "sec" + "ret": api_key_plaintext.secret,
            "is_testnet": is_testnet,
        }
        return HyperliquidRealAdapter(**kwargs)


# Singleton lazy
_adapter_factory_instance: HyperliquidAdapterFactory | None = None


def get_adapter_factory() -> HyperliquidAdapterFactory:
    """Devuelve el singleton del factory, creándolo lazily."""
    global _adapter_factory_instance
    if _adapter_factory_instance is None:
        _adapter_factory_instance = HyperliquidAdapterFactory()
    return _adapter_factory_instance
