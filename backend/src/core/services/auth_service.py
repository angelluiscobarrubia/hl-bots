"""Servicio de autenticación y gestión de usuarios."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.adapters.database.session import async_session_factory
from src.adapters.security.jwt import create_access_token, create_refresh_token, decode_token
from src.adapters.security.password import hash_password, verify_password
from src.adapters.security.permission_resolver import permission_resolver
from src.core.models import User


class AuthService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory

    async def authenticate(self, email: str, password: str) -> User | None:
        async with self._session_factory() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is None or not user.is_active:
                return None
            if not verify_password(password, user.password_hash):
                return None
            return user

    async def create_user(self, email: str, password: str, role: str = "user") -> User:
        async with self._session_factory() as session:
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                must_change_password=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    def issue_tokens(self, user: User) -> dict:
        return {
            "access_token": create_access_token(user.id, user.auth_version),
            "refresh_token": create_refresh_token(user.id, user.auth_version),
            "token_type": "bearer",
        }

    async def change_password(
        self, user: User, old_password: str, new_password: str
    ) -> None:
        if not verify_password(old_password, user.password_hash):
            raise ValueError("La contraseña actual es incorrecta")
        async with self._session_factory() as session:
            db_user = await session.get(User, user.id)
            db_user.password_hash = hash_password(new_password)
            db_user.must_change_password = False
            db_user.auth_version += 1
            await session.commit()

    async def reset_password(self, user: User, new_password: str) -> None:
        async with self._session_factory() as session:
            db_user = await session.get(User, user.id)
            db_user.password_hash = hash_password(new_password)
            db_user.must_change_password = True
            db_user.auth_version += 1
            await session.commit()

    async def revoke_tokens(self, user: User) -> None:
        async with self._session_factory() as session:
            db_user = await session.get(User, user.id)
            db_user.auth_version += 1
            await session.commit()

    async def touch_last_login(self, user: User) -> None:
        async with self._session_factory() as session:
            db_user = await session.get(User, user.id)
            db_user.last_login_at = datetime.now(timezone.utc)
            await session.commit()

    def get_permissions(self, user: User) -> frozenset[str]:
        return permission_resolver.get_permissions_for_role(user.role)

    def validate_refresh_token(self, token: str, user: User) -> bool:
        try:
            payload = decode_token(token)
        except Exception:
            return False
        if payload.get("type") != "refresh":
            return False
        if str(payload.get("sub")) != str(user.id):
            return False
        return payload.get("auth_version") == user.auth_version


auth_service = AuthService()
