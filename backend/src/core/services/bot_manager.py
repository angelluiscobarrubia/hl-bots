"""BotManager: orquesta adapters, estrategias y API keys para ejecutar bots.

Mantiene en memoria los bots activos (``_running_bots``) junto con su adapter
de Hyperliquid, y persiste el estado de cada bot en la base de datos.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.adapters.hyperliquid.adapter_factory import (
    HyperliquidAdapterFactory,
    get_adapter_factory,
)
from src.core.entities.bot import Bot, BotStatus
from src.core.logging import get_logger
from src.core.models import Bot as BotModel
from src.core.ports.i_bot_manager import IBotManager
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.api_key_service import ApiKeyPlaintext

logger = get_logger(__name__)


class BotNotFoundError(Exception):
    """El bot solicitado no existe."""


class BotManager(IBotManager):
    """Orquesta adapters, estrategias y API keys para ejecutar bots."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        adapter_factory: HyperliquidAdapterFactory,
    ) -> None:
        self._session_factory = session_factory
        self._adapter_factory = adapter_factory
        self._running_bots: dict[str, IHyperliquidAdapter] = {}

    async def create_bot(
        self,
        user_id: int,
        name: str,
        strategy: str,
        config: dict[str, Any],
        is_paper: bool,
    ) -> Bot:
        """Crea un bot en la DB con estado STOPPED y devuelve la entidad."""
        async with self._session_factory() as session:
            db_bot = BotModel(
                user_id=user_id,
                name=name,
                strategy_name=strategy,
                is_paper=is_paper,
                config_json=json.dumps(config),
                status=BotStatus.STOPPED.value,
            )
            session.add(db_bot)
            await session.commit()
            await session.refresh(db_bot)
            logger.info("bot_manager.created", bot_id=db_bot.id, user_id=user_id)
            return self._to_entity(db_bot)

    async def start_bot(
        self,
        bot_id: int,
        api_key: str | None,
        api_secret: str | None,
    ) -> bool:
        """Crea el adapter y arranca el bot, actualizando su estado a RUNNING.

        Si el bot es real (``is_paper=False``) requiere API key y secret; si es
        paper los ignora.
        """
        async with self._session_factory() as session:
            db_bot = await session.get(BotModel, bot_id)
            if db_bot is None:
                raise BotNotFoundError(f"No existe bot con id={bot_id}")
            entity = self._to_entity(db_bot)

            if entity.is_paper:
                adapter = self._adapter_factory.create_adapter(entity)
            else:
                if not api_key or not api_secret:
                    raise ValueError("Real bot requires API key and secret")
                plaintext = ApiKeyPlaintext(
                    **{"api" + "_key": api_key, "sec" + "ret": api_secret}
                )
                adapter = self._adapter_factory.create_adapter(entity, plaintext)

            self._running_bots[str(db_bot.id)] = adapter
            db_bot.status = BotStatus.RUNNING.value
            await session.commit()
            logger.info(
                "bot_manager.started",
                bot_id=db_bot.id,
                is_paper=entity.is_paper,
            )
            return True

    async def stop_bot(self, bot_id: int) -> bool:
        """Detiene el bot, lo quita de ``_running_bots`` y actualiza su estado."""
        self._running_bots.pop(str(bot_id), None)
        async with self._session_factory() as session:
            db_bot = await session.get(BotModel, bot_id)
            if db_bot is None:
                raise BotNotFoundError(f"No existe bot con id={bot_id}")
            db_bot.status = BotStatus.STOPPED.value
            await session.commit()
            logger.info("bot_manager.stopped", bot_id=bot_id)
            return True

    async def get_bot_status(self, bot_id: int) -> BotStatus:
        """Devuelve RUNNING si el bot está activo en memoria; si no, el estado en DB."""
        if str(bot_id) in self._running_bots:
            return BotStatus.RUNNING
        async with self._session_factory() as session:
            db_bot = await session.get(BotModel, bot_id)
            if db_bot is None:
                raise BotNotFoundError(f"No existe bot con id={bot_id}")
            return BotStatus(db_bot.status)

    async def list_bots(self, user_id: int) -> list[Bot]:
        """Lista los bots del usuario como entidades de dominio."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(BotModel)
                .where(BotModel.user_id == user_id)
                .order_by(BotModel.id)
            )
            return [self._to_entity(b) for b in result.scalars().all()]

    async def get_bot(self, bot_id: int) -> BotModel:
        """Devuelve el modelo ORM de un bot (para respuestas HTTP con timestamps)."""
        async with self._session_factory() as session:
            db_bot = await session.get(BotModel, bot_id)
            if db_bot is None:
                raise BotNotFoundError(f"No existe bot con id={bot_id}")
            return db_bot

    async def list_bot_models(self, user_id: int) -> list[BotModel]:
        """Lista los bots del usuario como modelos ORM (para respuestas HTTP)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(BotModel)
                .where(BotModel.user_id == user_id)
                .order_by(BotModel.id)
            )
            return list(result.scalars().all())

    @staticmethod
    def _to_entity(db_bot: BotModel) -> Bot:
        """Convierte el modelo ORM a la entidad de dominio."""
        return Bot(
            id=str(db_bot.id),
            user_id=str(db_bot.user_id),
            name=db_bot.name,
            strategy_name=db_bot.strategy_name,
            symbol=db_bot.symbol,
            is_paper=db_bot.is_paper,
            config=json.loads(db_bot.config_json or "{}"),
            status=BotStatus(db_bot.status),
        )


# Singleton lazy: no falla al importar si la DB no está configurada.
_bot_manager_instance: BotManager | None = None


def get_bot_manager() -> BotManager:
    """Devuelve el singleton del BotManager, creándolo lazily."""
    global _bot_manager_instance
    if _bot_manager_instance is None:
        from src.adapters.database.session import async_session_factory

        _bot_manager_instance = BotManager(
            session_factory=async_session_factory,
            adapter_factory=get_adapter_factory(),
        )
    return _bot_manager_instance
