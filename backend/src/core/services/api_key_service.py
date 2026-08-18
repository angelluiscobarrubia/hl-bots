"""Servicio para gestión de API keys cifradas.

Cifra al guardar, descifra solo cuando se necesita (al arrancar un bot).
Nunca expone plaintext en logs ni en respuestas HTTP.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.adapters.security.cipher import Cipher, get_cipher
from src.core.models import ApiKey


@dataclass
class ApiKeyPlaintext:
    """API key en texto plano. Solo existe en RAM, nunca en DB ni logs."""

    api_key: str
    secret: str


class ApiKeyNotFoundError(Exception):
    """La API key solicitada no existe."""


class ApiKeyAlreadyExistsError(Exception):
    """Ya existe una API key para ese bot_id."""


class ApiKeyService:
    """Gestiona el ciclo de vida de API keys cifradas."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: Cipher | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher or get_cipher()

    async def create_key(
        self,
        user_id: int,
        bot_id: str,
        exchange: str,
        api_key: str,
        secret: str,
    ) -> ApiKey:
        """Cifra y guarda una nueva API key."""
        encrypted_key = self._cipher.encrypt(api_key)
        encrypted_secret = self._cipher.encrypt(secret)
        async with self._session_factory() as session:
            db_key = ApiKey(
                user_id=user_id,
                bot_id=bot_id,
                exchange=exchange,
                encrypted_api_key=encrypted_key,
                encrypted_api_secret=encrypted_secret,
                is_active=True,
            )
            session.add(db_key)
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                raise ApiKeyAlreadyExistsError(
                    f"Ya existe una API key para bot_id={bot_id}"
                ) from e
            await session.refresh(db_key)
            return db_key

    async def get_key(self, bot_id: str) -> ApiKey:
        """Obtiene una API key por bot_id (sin descifrar)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ApiKey).where(ApiKey.bot_id == bot_id)
            )
            db_key = result.scalar_one_or_none()
            if db_key is None:
                raise ApiKeyNotFoundError(f"No existe API key para bot_id={bot_id}")
            return db_key

    async def list_keys(self, user_id: int | None = None) -> list[ApiKey]:
        """Lista API keys. Si user_id se da, filtra por dueño."""
        async with self._session_factory() as session:
            stmt = select(ApiKey).order_by(ApiKey.id)
            if user_id is not None:
                stmt = stmt.where(ApiKey.user_id == user_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def deactivate_key(self, bot_id: str) -> ApiKey:
        """Desactiva una API key (is_active=False) sin borrarla."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ApiKey).where(ApiKey.bot_id == bot_id)
            )
            db_key = result.scalar_one_or_none()
            if db_key is None:
                raise ApiKeyNotFoundError(f"No existe API key para bot_id={bot_id}")
            db_key.is_active = False
            await session.commit()
            await session.refresh(db_key)
            return db_key

    async def decrypt_key(self, bot_id: str) -> ApiKeyPlaintext:
        """Descifra una API key y devuelve el plaintext en RAM."""
        db_key = await self.get_key(bot_id)
        if not db_key.is_active:
            raise ApiKeyNotFoundError(
                f"API key para bot_id={bot_id} está desactivada"
            )
        return ApiKeyPlaintext(
            api_key=self._cipher.decrypt(db_key.encrypted_api_key),
            secret=self._cipher.decrypt(db_key.encrypted_api_secret),
        )


# Singleton lazy: no falla al importar si la clave no esta configurada.
_api_key_service_instance: ApiKeyService | None = None


def get_api_key_service() -> ApiKeyService:
    """Devuelve el singleton del servicio, creandolo lazily."""
    global _api_key_service_instance
    if _api_key_service_instance is None:
        from src.adapters.database.session import async_session_factory
        _api_key_service_instance = ApiKeyService(session_factory=async_session_factory)
    return _api_key_service_instance
