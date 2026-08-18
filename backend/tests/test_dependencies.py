"""Tests para las dependencias de autenticación y autorización."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from src.adapters.security.jwt import create_access_token, create_refresh_token
from src.api.dependencies import get_current_admin, get_current_user, require_permission
from src.core.models import User
from src.core.security.permissions import Perm


class TestGetCurrentUser:
    """Tests para get_current_user."""

    async def test_valid_token_returns_user(
        self, db_session: AsyncSession
    ) -> None:
        """Un token access válido retorna el usuario correspondiente."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="user",
            is_active=True,
            auth_version=0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        token = create_access_token(user.id, user.auth_version)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        result = await get_current_user(credentials, db_session)
        assert result.id == user.id
        assert result.email == "[REDACTED]"

    async def test_missing_credentials_401(
        self, db_session: AsyncSession
    ) -> None:
        """Sin credenciales se lanza HTTPException 401."""
        with pytest.raises(HTTPException) as exc:
            await get_current_user(None, db_session)
        assert exc.value.status_code == 401
        assert "No autenticado" in exc.value.detail

    async def test_invalid_token_401(
        self, db_session: AsyncSession
    ) -> None:
        """Un token inválido lanza HTTPException 401."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="garbage"
        )
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials, db_session)
        assert exc.value.status_code == 401
        assert "Token inválido o expirado" in exc.value.detail

    async def test_access_token_required(
        self, db_session: AsyncSession
    ) -> None:
        """Un token refresh no es aceptado como access."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="user",
            is_active=True,
            auth_version=0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        token = create_refresh_token(user.id, user.auth_version)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials, db_session)
        assert exc.value.status_code == 401
        assert "Token inválido" in exc.value.detail

    async def test_inactive_user_401(
        self, db_session: AsyncSession
    ) -> None:
        """Un usuario inactivo lanza HTTPException 401."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="user",
            is_active=False,
            auth_version=0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        token = create_access_token(user.id, user.auth_version)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials, db_session)
        assert exc.value.status_code == 401
        assert "Usuario inactivo o inexistente" in exc.value.detail

    async def test_stale_auth_version_401(
        self, db_session: AsyncSession
    ) -> None:
        """Un token con auth_version desactualizado lanza HTTPException 401."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="user",
            is_active=True,
            auth_version=1,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Crear token con auth_version anterior al del usuario
        token = create_access_token(user.id, auth_version=0)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials, db_session)
        assert exc.value.status_code == 401
        assert "Token revocado" in exc.value.detail


class TestRequirePermission:
    """Tests para require_permission."""

    async def test_require_permission_allows(
        self, db_session: AsyncSession
    ) -> None:
        """Un usuario con el rol adecuado pasa el control de permiso."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="user",
            is_active=True,
            auth_version=0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        dep = require_permission(Perm.BOTS_CREATE)
        result = await dep(user)
        assert result.id == user.id

    async def test_require_permission_denies(
        self, db_session: AsyncSession
    ) -> None:
        """Un usuario sin el permiso recibe HTTPException 403."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="user",
            is_active=True,
            auth_version=0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        dep = require_permission(Perm.USERS_MANAGE)
        with pytest.raises(HTTPException) as exc:
            await dep(user)
        assert exc.value.status_code == 403
        assert "Permiso denegado" in exc.value.detail


class TestGetCurrentAdmin:
    """Tests para get_current_admin."""

    async def test_get_current_admin_ok(
        self, db_session: AsyncSession
    ) -> None:
        """Un usuario admin pasa el control."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="admin",
            is_active=True,
            auth_version=0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        result = await get_current_admin(user)
        assert result.id == user.id

    async def test_get_current_admin_forbidden(
        self, db_session: AsyncSession
    ) -> None:
        """Un usuario no admin recibe HTTPException 403."""
        user = User(
            email="[REDACTED]",
            password_hash="hash",
            role="user",
            is_active=True,
            auth_version=0,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        with pytest.raises(HTTPException) as exc:
            await get_current_admin(user)
        assert exc.value.status_code == 403
        assert "Se requiere rol admin" in exc.value.detail
