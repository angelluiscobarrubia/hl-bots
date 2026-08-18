"""Tests para AuthService."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.adapters.security.jwt import decode_token
from src.adapters.security.password import verify_password
from src.core.models import Base, User
from src.core.services.auth_service import AuthService


@pytest.fixture
async def auth_session_factory() -> async_sessionmaker[AsyncSession]:
    """Fixture que provee un async_sessionmaker SQLite en memoria con esquema creado."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def svc(auth_session_factory: async_sessionmaker[AsyncSession]) -> AuthService:
    return AuthService(session_factory=auth_session_factory)


class TestCreateUser:
    async def test_create_user(self, svc: AuthService) -> None:
        """create_user crea un usuario con los valores esperados."""
        user = await svc.create_user("[REDACTED]", "secret123")

        assert user.email == "[REDACTED]"
        assert user.password_hash != "secret123"  # noqa: S105
        assert user.must_change_password is True
        assert user.role == "user"


class TestAuthenticate:
    async def test_authenticate_success(self, svc: AuthService) -> None:
        """authenticate retorna el usuario con credenciales correctas."""
        await svc.create_user("[REDACTED]", "secret123")
        user = await svc.authenticate("[REDACTED]", "secret123")
        assert user is not None
        assert user.email == "[REDACTED]"

    async def test_authenticate_wrong_password(self, svc: AuthService) -> None:
        """authenticate retorna None con password incorrecta."""
        await svc.create_user("[REDACTED]", "secret123")
        user = await svc.authenticate("[REDACTED]", "wrongpassword")
        assert user is None

    async def test_authenticate_inactive(
        self,
        svc: AuthService,
        auth_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """authenticate retorna None para usuario inactivo."""
        await svc.create_user("[REDACTED]", "secret123")
        async with auth_session_factory() as session:
            db_user = await session.get(User, 1)
            db_user.is_active = False
            await session.commit()

        user = await svc.authenticate("[REDACTED]", "secret123")
        assert user is None


class TestIssueTokens:
    async def test_issue_tokens(self, svc: AuthService) -> None:
        """issue_tokens emite access y refresh tokens válidos."""
        user = await svc.create_user("[REDACTED]", "secret123")
        tokens = svc.issue_tokens(user)

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"  # noqa: S105

        access_payload = decode_token(tokens["access_token"])
        refresh_payload = decode_token(tokens["refresh_token"])

        assert access_payload["sub"] == str(user.id)
        assert refresh_payload["sub"] == str(user.id)


class TestChangePassword:
    async def test_change_password_success(
        self,
        svc: AuthService,
        auth_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """change_password actualiza el hash y versiona."""
        user = await svc.create_user("[REDACTED]", "oldpass")
        old_auth_version = user.auth_version

        await svc.change_password(user, "oldpass", "newpass")

        async with auth_session_factory() as session:
            reloaded = await session.get(User, user.id)
            assert reloaded.must_change_password is False
            assert reloaded.auth_version == old_auth_version + 1
            assert verify_password("newpass", reloaded.password_hash)

    async def test_change_password_wrong_old(self, svc: AuthService) -> None:
        """change_password con old incorrecta lanza ValueError."""
        user = await svc.create_user("[REDACTED]", "oldpass")

        with pytest.raises(ValueError, match="La contraseña actual es incorrecta"):
            await svc.change_password(user, "wrong", "newpass")


class TestResetPassword:
    async def test_reset_password(
        self,
        svc: AuthService,
        auth_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """reset_password fuerza cambio y versiona."""
        user = await svc.create_user("[REDACTED]", "oldpass")
        old_auth_version = user.auth_version

        await svc.reset_password(user, "newpass")

        async with auth_session_factory() as session:
            reloaded = await session.get(User, user.id)
            assert reloaded.must_change_password is True
            assert reloaded.auth_version == old_auth_version + 1
            assert verify_password("newpass", reloaded.password_hash)


class TestValidateRefreshToken:
    async def test_valid_refresh_token(self, svc: AuthService) -> None:
        """validate_refresh_token retorna True para refresh token válido."""
        user = await svc.create_user("[REDACTED]", "secret123")
        tokens = svc.issue_tokens(user)
        assert svc.validate_refresh_token(tokens["refresh_token"], user) is True

    async def test_access_token_rejected(self, svc: AuthService) -> None:
        """validate_refresh_token retorna False para access token."""
        user = await svc.create_user("[REDACTED]", "secret123")
        tokens = svc.issue_tokens(user)
        assert svc.validate_refresh_token(tokens["access_token"], user) is False

    async def test_stale_auth_version_rejected(
        self,
        svc: AuthService,
        auth_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """validate_refresh_token retorna False con auth_version desactualizado."""
        user = await svc.create_user("[REDACTED]", "secret123")
        tokens = svc.issue_tokens(user)
        # Increment auth_version para simular un token desactualizado
        await svc.revoke_tokens(user)
        async with auth_session_factory() as session:
            reloaded = await session.get(User, user.id)
        assert svc.validate_refresh_token(tokens["refresh_token"], reloaded) is False
