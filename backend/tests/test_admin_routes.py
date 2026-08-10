"""Tests para las rutas de administración de usuarios."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.adapters.security.jwt import create_access_token
from src.core.models import Base
from src.core.services.auth_service import auth_service

TEST_PASS = "[REDACTED]"


def _unique_email(prefix: str = "test") -> str:
    """Genera un email único para evitar conflictos de UNIQUE constraint."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


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


class TestCreateUser:
    """Tests para POST /admin/users."""

    async def test_create_user_as_admin(self, client: AsyncClient) -> None:
        """Admin puede crear un nuevo usuario."""
        admin_email = _unique_email("admin")
        user_email = _unique_email("user")
        admin = await auth_service.create_user(admin_email, TEST_PASS, role="admin")
        admin_token = create_access_token(admin.id, admin.auth_version)

        response = await client.post(
            "/admin/users",
            json={"email": user_email, "password": TEST_PASS, "role": "user"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == user_email
        assert body["role"] == "user"
        assert body["must_change_password"] is True
        assert body["is_active"] is True

    async def test_create_user_duplicate_email(self, client: AsyncClient) -> None:
        """Crear usuario con email duplicado retorna 409."""
        admin_email = _unique_email("admin")
        dup_email = _unique_email("dup")
        admin = await auth_service.create_user(admin_email, TEST_PASS, role="admin")
        admin_token = create_access_token(admin.id, admin.auth_version)
        await auth_service.create_user(dup_email, TEST_PASS)

        response = await client.post(
            "/admin/users",
            json={"email": dup_email, "password": TEST_PASS, "role": "user"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        assert "ya existe" in response.json()["detail"]

    async def test_create_user_forbidden_for_normal_user(
        self, client: AsyncClient
    ) -> None:
        """Usuario normal no puede crear usuarios (403)."""
        user_email = _unique_email("normal")
        other_email = _unique_email("other")
        user = await auth_service.create_user(user_email, TEST_PASS, role="user")
        user_token = create_access_token(user.id, user.auth_version)

        response = await client.post(
            "/admin/users",
            json={"email": other_email, "password": "newpass123", "role": "user"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert response.status_code == 403
        assert "Permiso denegado" in response.json()["detail"]


class TestListUsers:
    """Tests para GET /admin/users."""

    async def test_list_users(self, client: AsyncClient) -> None:
        """Admin puede listar todos los usuarios."""
        admin_email = _unique_email("admin")
        user2_email = _unique_email("user2")
        user3_email = _unique_email("user3")
        admin = await auth_service.create_user(admin_email, TEST_PASS, role="admin")
        admin_token = create_access_token(admin.id, admin.auth_version)
        await auth_service.create_user(user2_email, "pass1234", role="user")
        await auth_service.create_user(user3_email, "pass1234", role="user")

        response = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) >= 3  # admin + 2 users
        emails = [u["email"] for u in body]
        assert user2_email in emails
        assert user3_email in emails


class TestUpdateUser:
    """Tests para PATCH /admin/users/{user_id}."""

    async def test_update_user_deactivate(self, client: AsyncClient) -> None:
        """Admin puede desactivar un usuario."""
        admin_email = _unique_email("admin")
        user_email = _unique_email("user")
        admin = await auth_service.create_user(admin_email, TEST_PASS, role="admin")
        admin_token = create_access_token(admin.id, admin.auth_version)
        user = await auth_service.create_user(user_email, TEST_PASS, role="user")

        response = await client.patch(
            f"/admin/users/{user.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        # Verificar que el usuario desactivado no puede hacer login
        login_resp = await client.post(
            "/auth/login",
            json={"email": user_email, "password": TEST_PASS},
        )
        assert login_resp.status_code == 401

    async def test_update_user_not_found(self, client: AsyncClient) -> None:
        """PATCH a usuario inexistente retorna 404."""
        admin_email = _unique_email("admin")
        admin = await auth_service.create_user(admin_email, TEST_PASS, role="admin")
        admin_token = create_access_token(admin.id, admin.auth_version)

        response = await client.patch(
            "/admin/users/9999",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"].lower()


class TestResetPassword:
    """Tests para POST /admin/users/{user_id}/reset-password."""

    async def test_reset_password_invalidates_tokens(
        self, client: AsyncClient
    ) -> None:
        """Reset de password invalida tokens anteriores."""
        admin_email = _unique_email("admin")
        user_email = _unique_email("user")
        admin = await auth_service.create_user(admin_email, TEST_PASS, role="admin")
        admin_token = create_access_token(admin.id, admin.auth_version)
        user = await auth_service.create_user(user_email, TEST_PASS, role="user")

        # Login para obtener access token del usuario normal
        login_resp = await client.post(
            "/auth/login",
            json={"email": user_email, "password": TEST_PASS},
        )
        assert login_resp.status_code == 200
        old_access = login_resp.json()["access_token"]

        # Admin resetea la contraseña
        response = await client.post(
            f"/admin/users/{user.id}/reset-password",
            json={"new_password": "newpass123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

        # El viejo access token ya no funciona
        me_resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {old_access}"},
        )
        assert me_resp.status_code == 401

        # Login con la nueva contraseña funciona
        login_resp2 = await client.post(
            "/auth/login",
            json={"email": user_email, "password": "newpass123"},
        )
        assert login_resp2.status_code == 200
