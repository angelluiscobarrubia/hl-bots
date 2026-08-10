"""Tests para el modelo User."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.models import User


class TestUserModel:
    """Suite de tests para el modelo User."""

    async def test_create_user_defaults(self, db_session: AsyncSession) -> None:
        """Crea un usuario y verifica valores por defecto."""
        user = User(email="[REDACTED]", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.role == "user"
        assert user.is_active is True
        assert user.must_change_password is False
        assert user.auth_version == 0
        assert user.created_at is not None

    async def test_email_unique(self, db_session: AsyncSession) -> None:
        """Dos usuarios con el mismo email deben violar la unicidad."""
        user1 = User(email="[REDACTED]", password_hash="x")
        db_session.add(user1)
        await db_session.commit()

        user2 = User(email="[REDACTED]", password_hash="y")
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
