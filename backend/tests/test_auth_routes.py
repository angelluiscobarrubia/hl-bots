"""Tests para las rutas de autenticación."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.adapters.security.jwt import create_access_token, create_refresh_token
from src.core.models import Base, User
from src.core.services.auth_service import auth_service

TEST_EMAIL = "x@y.com"
TEST_PASS = "abc12345"


@pytest.fixture
async def test_engine():
    """Crea un engine SQLite en memoria para operaciones directas en tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    """Session factory basada en el mismo engine que usa el client fixture."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


class TestLogin:
    """Tests para POST /auth/login."""

    async def test_login_success(self, client: AsyncClient) -> None:
        """Login con credenciales correctas retorna tokens y datos del usuario."""
        await auth_service.create_user(TEST_EMAIL, TEST_PASS)

        response = await client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASS},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == TEST_EMAIL
        assert body["must_change_password"] is True

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        """Login con password incorrecta retorna 401."""
        await auth_service.create_user(TEST_EMAIL, TEST_PASS)

        response = await client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": "wrongpass"},
        )
        assert response.status_code == 401
        assert "Credenciales inválidas" in response.json()["detail"]

    async def test_login_inactive_user(
        self,
        client: AsyncClient,
    ) -> None:
        """Login de usuario inactivo retorna 401."""
        user = await auth_service.create_user(TEST_EMAIL, TEST_PASS)
        # Desactivar el usuario en la base de datos
        async with auth_service._session_factory() as session:
            db_user = await session.get(User, user.id)
            db_user.is_active = False
            await session.commit()

        response = await client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASS},
        )
        assert response.status_code == 401
        assert "Credenciales inválidas" in response.json()["detail"]


class TestRefresh:
    """Tests para POST /auth/refresh."""

    async def test_refresh_success(self, client: AsyncClient) -> None:
        """Refresh con refresh_token válido retorna nuevos tokens."""
        user = await auth_service.create_user(TEST_EMAIL, TEST_PASS)
        valid_refresh = create_refresh_token(user.id, user.auth_version)

        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": valid_refresh},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["user"]["email"] == TEST_EMAIL

    async def test_refresh_with_access_token(self, client: AsyncClient) -> None:
        """Usar un access_token como refresh_token retorna 401."""
        user = await auth_service.create_user(TEST_EMAIL, TEST_PASS)
        access = create_access_token(user.id, user.auth_version)

        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": access},
        )
        assert response.status_code == 401
        assert "Refresh token inválido" in response.json()["detail"]


class TestMe:
    """Tests para GET /auth/me."""

    async def test_me_authenticated(self, client: AsyncClient) -> None:
        """GET /auth/me con token válido retorna el usuario."""
        user = await auth_service.create_user(TEST_EMAIL, TEST_PASS)
        access = create_access_token(user.id, user.auth_version)

        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == TEST_EMAIL

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        """GET /auth/me sin token retorna 401."""
        response = await client.get("/auth/me")
        assert response.status_code == 401
        assert "No autenticado" in response.json()["detail"]


class TestChangePassword:
    """Tests para POST /auth/change-password."""

    async def test_change_password_success(self, client: AsyncClient) -> None:
        """Cambio de contraseña exitoso retorna 204 y permite login con nueva pass."""
        await auth_service.create_user(TEST_EMAIL, "oldpass123")
        login_resp = await client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": "oldpass123"},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        access = login_data["access_token"]

        response = await client.post(
            "/auth/change-password",
            json={"old_password": "oldpass123", "new_password": "newpass123"},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert response.status_code == 204

        # Verificar que se puede login con la nueva contraseña
        login_resp2 = await client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": "newpass123"},
        )
        assert login_resp2.status_code == 200

    async def test_change_password_wrong_old(self, client: AsyncClient) -> None:
        """Cambio de contraseña con old_password incorrecta retorna 400."""
        await auth_service.create_user(TEST_EMAIL, "oldpass123")
        login_resp = await client.post(
            "/auth/login",
            json={"email": TEST_EMAIL, "password": "oldpass123"},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        access = login_data["access_token"]

        response = await client.post(
            "/auth/change-password",
            json={"old_password": "wrongpass", "new_password": "newpass123"},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert response.status_code == 400
        assert "La contraseña actual es incorrecta" in response.json()["detail"]
