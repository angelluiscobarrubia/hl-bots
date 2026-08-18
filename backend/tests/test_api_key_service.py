"""Tests para ApiKeyService."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.adapters.security.cipher import Cipher
from src.core.models import Base
from src.core.services.api_key_service import (
    ApiKeyAlreadyExistsError,
    ApiKeyNotFoundError,
    ApiKeyService,
)

TEST_KEY = "vL3SzKwCsfVozQCooiOeXRfzpxazYeiYeZBM_oly3AE="
TEST_CIPHER = Cipher(key=TEST_KEY)


@pytest.fixture
async def session_factory():
    """Factory de sesiones SQLite en memoria."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def service(session_factory):
    """ApiKeyService con cipher de test."""
    return ApiKeyService(session_factory=session_factory, cipher=TEST_CIPHER)


class TestApiKeyServiceCreate:
    """Tests de create_key."""

    async def test_create_key_stores_ciphertext_not_plaintext(self, service):
        """create_key cifra y guarda ciphertext, nunca plaintext."""
        db_key = await service.create_key(
            user_id=1,
            bot_id="bot-001",
            exchange="hyperliquid",
            api_key="original-key",
            secret="original-secret",
        )
        assert db_key.id is not None
        assert db_key.bot_id == "bot-001"
        assert db_key.is_active is True
        # El ciphertext NO debe contener el plaintext
        assert "original-key" not in db_key.encrypted_api_key
        assert "original-secret" not in db_key.encrypted_api_secret

    async def test_create_key_duplicate_bot_id_raises(self, service):
        """Dos claves con el mismo bot_id lanzan ApiKeyAlreadyExistsError."""
        await service.create_key(
            user_id=1, bot_id="bot-dup", exchange="hyperliquid",
            api_key="k1", secret="s1",
        )
        with pytest.raises(ApiKeyAlreadyExistsError):
            await service.create_key(
                user_id=2, bot_id="bot-dup", exchange="hyperliquid",
                api_key="k2", secret="s2",
            )


class TestApiKeyServiceGet:
    """Tests de get_key."""

    async def test_get_key_returns_ciphertext(self, service):
        """get_key devuelve el modelo con ciphertext (no descifra)."""
        await service.create_key(
            user_id=1, bot_id="bot-get", exchange="hyperliquid",
            api_key="k", secret="s",
        )
        db_key = await service.get_key("bot-get")
        assert db_key.bot_id == "bot-get"
        assert db_key.encrypted_api_key.startswith("gAAAAA")  # Fernet prefix

    async def test_get_key_not_found_raises(self, service):
        """get_key con bot_id inexistente lanza ApiKeyNotFoundError."""
        with pytest.raises(ApiKeyNotFoundError):
            await service.get_key("nonexistent")


class TestApiKeyServiceList:
    """Tests de list_keys."""

    async def test_list_keys_returns_all(self, service):
        """list_keys sin filtro devuelve todas las claves."""
        for i in range(3):
            await service.create_key(
                user_id=1, bot_id=f"bot-{i}", exchange="hyperliquid",
                api_key=f"k{i}", secret=f"s{i}",
            )
        keys = await service.list_keys()
        assert len(keys) == 3

    async def test_list_keys_filtered_by_user(self, service):
        """list_keys con user_id filtra por dueño."""
        await service.create_key(
            user_id=1, bot_id="bot-u1", exchange="hyperliquid",
            api_key="k", secret="s",
        )
        await service.create_key(
            user_id=2, bot_id="bot-u2", exchange="hyperliquid",
            api_key="k", secret="s",
        )
        keys_u1 = await service.list_keys(user_id=1)
        keys_u2 = await service.list_keys(user_id=2)
        assert len(keys_u1) == 1
        assert len(keys_u2) == 1
        assert keys_u1[0].bot_id == "bot-u1"
        assert keys_u2[0].bot_id == "bot-u2"


class TestApiKeyServiceDeactivate:
    """Tests de deactivate_key."""

    async def test_deactivate_key_sets_inactive(self, service):
        """deactivate_key pone is_active=False."""
        await service.create_key(
            user_id=1, bot_id="bot-deact", exchange="hyperliquid",
            api_key="k", secret="s",
        )
        db_key = await service.deactivate_key("bot-deact")
        assert db_key.is_active is False

    async def test_deactivate_key_not_found_raises(self, service):
        """deactivate_key con bot_id inexistente lanza ApiKeyNotFoundError."""
        with pytest.raises(ApiKeyNotFoundError):
            await service.deactivate_key("nonexistent")


class TestApiKeyServiceDecrypt:
    """Tests de decrypt_key."""

    async def test_decrypt_key_returns_plaintext(self, service):
        """decrypt_key devuelve el plaintext original."""
        await service.create_key(
            user_id=1, bot_id="bot-dec", exchange="hyperliquid",
            api_key="original-key", secret="original-secret",
        )
        plaintext = await service.decrypt_key("bot-dec")
        assert plaintext.api_key == "original-key"
        assert plaintext.secret == "original-secret"

    async def test_decrypt_inactive_key_raises(self, service):
        """decrypt_key en clave desactivada lanza ApiKeyNotFoundError."""
        await service.create_key(
            user_id=1, bot_id="bot-inactive", exchange="hyperliquid",
            api_key="k", secret="s",
        )
        await service.deactivate_key("bot-inactive")
        with pytest.raises(ApiKeyNotFoundError):
            await service.decrypt_key("bot-inactive")

    async def test_decrypt_nonexistent_raises(self, service):
        """decrypt_key con bot_id inexistente lanza ApiKeyNotFoundError."""
        with pytest.raises(ApiKeyNotFoundError):
            await service.decrypt_key("nonexistent")
