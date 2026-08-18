"""Tests para las rutas /admin/api-keys."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.adapters.security.cipher import Cipher
from src.core.models import Base
from src.core.services.api_key_service import ApiKeyService

TEST_KEY = "vL3SzKwCsfVozQCooiOeXRfzpxazYeiYeZBM_oly3AE="
TEST_CIPHER = Cipher(key=TEST_KEY)


async def _bootstrap_admin(auth_service, email: str, password: str) -> None:
    """Crea el primer admin directamente via el servicio (bootstrap)."""
    await auth_service.create_user(email, password, role="admin")


async def _login(client: AsyncClient, email: str, password: str) -> str:
    """Hace login y devuelve el access_token."""
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    return data["access_token"]


@pytest.fixture
async def api_key_client():
    """Cliente HTTP con router de api-keys y admin user pre-creado."""
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.adapters.database.session import get_db
    from src.api.limiter import limiter
    from src.api.routes.admin_routes import router as admin_router
    from src.api.routes.api_key_routes import router as api_key_router
    from src.api.routes.auth_routes import router as auth_router
    from src.core.services.auth_service import auth_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(engine, expire_on_commit=False)
    auth_service._session_factory = test_factory

    # Patch api_key_service singleton
    test_service = ApiKeyService(session_factory=test_factory, cipher=TEST_CIPHER)
    import src.core.services.api_key_service as svc_module
    svc_module._api_key_service_instance = test_service

    # Bootstrap: crear admin directamente
    await _bootstrap_admin(auth_service, "admin@test.com", "adminpass123")

    limiter.reset()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(api_key_router)

    async def _override_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()


class TestApiKeyRoutes:
    """Tests de las rutas /admin/api-keys."""

    async def test_create_api_key_as_admin(self, api_key_client):
        """Admin puede crear una API key."""
        token = await _login(api_key_client, "admin@test.com", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        resp = await api_key_client.post(
            "/admin/api-keys",
            headers=headers,
            json={
                "user_id": 1,
                "bot_id": "bot-001",
                "exchange": "hyperliquid",
                "api_key": "plaintext-key",
                "secret": "plaintext-api_secret",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bot_id"] == "bot-001"
        assert data["is_active"] is True
        # La respuesta NO debe contener plaintext
        assert "plaintext-key" not in resp.text
        assert "plaintext-api_secret" not in resp.text

    async def test_create_api_key_duplicate_bot_id(self, api_key_client):
        """Crear clave con bot_id duplicado devuelve 409."""
        token = await _login(api_key_client, "admin@test.com", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        body = {
            "user_id": 1,
            "bot_id": "bot-dup",
            "exchange": "hyperliquid",
            "api_key": "k",
            "secret": "s",
        }
        resp1 = await api_key_client.post("/admin/api-keys", headers=headers, json=body)
        assert resp1.status_code == 201
        resp2 = await api_key_client.post("/admin/api-keys", headers=headers, json=body)
        assert resp2.status_code == 409

    async def test_create_api_key_forbidden_for_normal_user(self, api_key_client):
        """Usuario normal no puede crear API keys (403)."""
        from src.core.services.auth_service import auth_service
        await auth_service.create_user("user@test.com", "userpass123", role="user")
        token = await _login(api_key_client, "user@test.com", "userpass123")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await api_key_client.post(
            "/admin/api-keys",
            headers=headers,
            json={
                "user_id": 2,
                "bot_id": "bot-002",
                "exchange": "hyperliquid",
                "api_key": "k",
                "secret": "s",
            },
        )
        assert resp.status_code == 403

    async def test_list_api_keys(self, api_key_client):
        """Admin puede listar API keys."""
        token = await _login(api_key_client, "admin@test.com", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        for i in range(2):
            await api_key_client.post(
                "/admin/api-keys",
                headers=headers,
                json={
                    "user_id": 1,
                    "bot_id": f"bot-{i}",
                    "exchange": "hyperliquid",
                    "api_key": f"k{i}",
                    "secret": f"s{i}",
                },
            )
        resp = await api_key_client.get("/admin/api-keys", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["keys"]) == 2

    async def test_get_api_key_by_bot_id(self, api_key_client):
        """Admin puede obtener una API key por bot_id."""
        token = await _login(api_key_client, "admin@test.com", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        await api_key_client.post(
            "/admin/api-keys",
            headers=headers,
            json={
                "user_id": 1,
                "bot_id": "bot-get",
                "exchange": "hyperliquid",
                "api_key": "k",
                "secret": "s",
            },
        )
        resp = await api_key_client.get("/admin/api-keys/bot-get", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["bot_id"] == "bot-get"

    async def test_get_api_key_not_found(self, api_key_client):
        """GET con bot_id inexistente devuelve 404."""
        token = await _login(api_key_client, "admin@test.com", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        resp = await api_key_client.get("/admin/api-keys/nonexistent", headers=headers)
        assert resp.status_code == 404

    async def test_deactivate_api_key(self, api_key_client):
        """Admin puede desactivar una API key."""
        token = await _login(api_key_client, "admin@test.com", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        await api_key_client.post(
            "/admin/api-keys",
            headers=headers,
            json={
                "user_id": 1,
                "bot_id": "bot-deact",
                "exchange": "hyperliquid",
                "api_key": "k",
                "secret": "s",
            },
        )
        resp = await api_key_client.post(
            "/admin/api-keys/bot-deact/deactivate", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_create_api_key_unauthenticated(self, api_key_client):
        """Sin token devuelve 401."""
        resp = await api_key_client.post(
            "/admin/api-keys",
            json={
                "user_id": 1,
                "bot_id": "bot-001",
                "exchange": "hyperliquid",
                "api_key": "k",
                "secret": "s",
            },
        )
        assert resp.status_code == 401
