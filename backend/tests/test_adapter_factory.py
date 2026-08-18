"""Tests para el HyperliquidAdapterFactory."""

import pytest
from src.adapters.hyperliquid.adapter_factory import (
    HyperliquidAdapterFactory,
    get_adapter_factory,
)
from src.adapters.hyperliquid.hyperliquid_real_adapter import HyperliquidRealAdapter
from src.adapters.hyperliquid.paper_broker_adapter import PaperBrokerAdapter
from src.core.config import settings
from src.core.entities.bot import Bot
from src.core.services.api_key_service import ApiKeyPlaintext


def _make_bot(is_paper: bool = True, config: dict | None = None) -> Bot:
    """Construye un Bot mínimo para los tests."""
    return Bot(
        id="bot-1",
        user_id="user-1",
        name="Test Bot",
        strategy_name="test_strategy",
        is_paper=is_paper,
        config=config or {},
    )


def _make_api_key() -> ApiKeyPlaintext:
    """Construye una ApiKeyPlaintext de prueba."""
    return ApiKeyPlaintext(**{"api_key": "test-api-key", "secret": "test-secret"})


def test_creates_paper_adapter_for_paper_bot() -> None:
    """Un bot con is_paper=True devuelve un PaperBrokerAdapter."""
    factory = HyperliquidAdapterFactory()
    adapter = factory.create_adapter(_make_bot(is_paper=True))
    assert isinstance(adapter, PaperBrokerAdapter)


def test_creates_real_adapter_for_real_bot() -> None:
    """Un bot real con ApiKeyPlaintext devuelve un HyperliquidRealAdapter."""
    factory = HyperliquidAdapterFactory()
    creds = _make_api_key()
    adapter = factory.create_adapter(_make_bot(is_paper=False), creds)
    assert isinstance(adapter, HyperliquidRealAdapter)


def test_real_adapter_requires_api_key() -> None:
    """Un bot real sin API key lanza ValueError."""
    factory = HyperliquidAdapterFactory()
    with pytest.raises(ValueError, match="requires API key"):
        factory.create_adapter(_make_bot(is_paper=False), None)


def test_uses_testnet_url_when_configured() -> None:
    """Un bot con testnet=True usa la URL de testnet."""
    factory = HyperliquidAdapterFactory()
    creds = _make_api_key()
    adapter = factory.create_adapter(
        _make_bot(is_paper=False, config={"testnet": True}), creds
    )
    assert isinstance(adapter, HyperliquidRealAdapter)
    assert adapter.base_url == settings.hyperliquid_testnet_url


def test_uses_mainnet_url_by_default() -> None:
    """Un bot sin testnet configurado usa la URL de mainnet."""
    factory = HyperliquidAdapterFactory()
    creds = _make_api_key()
    adapter = factory.create_adapter(_make_bot(is_paper=False), creds)
    assert isinstance(adapter, HyperliquidRealAdapter)
    assert adapter.base_url == settings.hyperliquid_mainnet_url


def test_get_adapter_factory_is_singleton() -> None:
    """get_adapter_factory devuelve siempre la misma instancia."""
    assert get_adapter_factory() is get_adapter_factory()
