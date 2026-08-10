"""Tests para la capa de sesión async de base de datos."""

from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.adapters.database.session import get_db


class TestDbSessionFixture:
    """Verifica que el fixture db_session funciona correctamente."""

    async def test_trivial_query(self, db_session: AsyncSession) -> None:
        """Ejecuta SELECT 1 y verifica que la base de datos responde."""
        result = await db_session.execute(text("SELECT 1"))
        row = result.one()
        assert row[0] == 1

    async def test_get_db_yields_session(self) -> None:
        """Verifica que get_db() produce una AsyncSession válida.

        Se parchea async_session_factory con SQLite en memoria para
        evitar depender de una base de datos real.
        """
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        mock_factory = async_sessionmaker(engine, expire_on_commit=False)

        with patch(
            "src.adapters.database.session.async_session_factory",
            mock_factory,
        ):
            gen = get_db()
            assert isinstance(gen, AsyncIterator)

            session = await gen.__anext__()
            assert isinstance(session, AsyncSession)

            # Ejecuta una consulta trivial para confirmar que funciona
            result = await session.execute(text("SELECT 1"))
            row = result.one()
            assert row[0] == 1

            # Cierra el generador
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()
