"""Dependencias de autenticación y autorización para FastAPI."""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.database.session import get_db
from src.adapters.security.jwt import decode_token
from src.core.models import User
from src.core.services.auth_service import auth_service

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado"
        )
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado"
        ) from None
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        )
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o inexistente",
        )
    if payload.get("auth_version") != user.auth_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revocado"
        )
    return user


def require_permission(permission: str) -> Callable:
    """Retorna una dependencia que verifica que el usuario tenga el permiso indicado."""

    async def _dependency(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if permission not in auth_service.get_permissions(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permiso denegado"
            )
        return user

    return _dependency


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol admin"
        )
    return user
