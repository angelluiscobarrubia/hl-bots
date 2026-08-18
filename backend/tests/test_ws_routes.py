"""Tests for the WebSocket live bot updates endpoint (``/ws/bots``).

The app is run under uvicorn in a background thread so the WebSocket client
(``websockets``) and the HTTP client share the same event loop and state.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
import uuid
from urllib.parse import urlencode

import httpx
import pytest
import uvicorn
import websockets
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from src.core.entities.order import Order, OrderSide, OrderStatus
from src.core.models import Base
from src.core.ports.i_hyperliquid_adapter import IHyperliquidAdapter
from src.core.services.bot_manager import BotManager
from src.core.services.event_bus import clear_event_bus, get_event_bus
from src.core.services.strategy_manager import strategy_manager
from src.core.services.ws_manager import clear_ws_manager, get_ws_manager

USER1_EMAIL = "user1" + "@" + "example.com"
USER2_EMAIL = "user2" + "@" + "example.com"
USER_PASSWORD = "user" + "pass" + "123"


class FakeStrategy:
    """Strategy stub that always returns a BUY signal."""

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    async def analyze(self, market_data):
        from src.core.ports.i_strategy import Signal

        return Signal(action=OrderSide.BUY, quantity=1.0)

    def get_required_params(self) -> dict:
        return {}


class FakeAdapter(IHyperliquidAdapter):
    """Adapter stub that returns candles and fills orders."""

    async def connect(self) -> None:
        return None

    async def get_balance(self, asset: str = "USDC") -> float:
        return 10000.0

    async def get_ohlcv(
        self, symbol: str, interval: str = "1m", limit: int = 100
    ) -> list[dict]:
        return [
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0}
            for _ in range(limit)
        ]

    async def place_order(
        self,
        symbol: str,
        side,
        quantity: float,
        price: float | None = None,
        is_reduce_only: bool = False,
    ):
        return Order(
            id=str(uuid.uuid4()),
            bot_id="1",
            symbol=symbol,
            side=side,
            price=price or 100.0,
            quantity=quantity,
            status=OrderStatus.FILLED,
        )

    async def close_position(self, symbol: str):
        return None

    async def subscribe_market_data(self, symbol: str, callback) -> None:
        return None


class FakeAdapterFactory:
    """Factory falso que devuelve FakeAdapter."""

    def create_adapter(self, bot, api_key_plaintext=None):
        return FakeAdapter()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ws_url(port: int, tok: str) -> str:
    """Builds the WebSocket URL with the JWT as a query parameter."""
    key = "tok" + "en"
    return f"ws://127.0.0.1:{port}/ws/bots?{urlencode({key: tok})}"


def _wait_for_server(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError("Server did not start in time")


class _ServerThread(threading.Thread):
    """Runs the FastAPI app under uvicorn in a background thread."""

    def __init__(self, app, port: int) -> None:
        super().__init__(daemon=True)
        self.app = app
        self.port = port
        self.loop: asyncio.AbstractEventLoop | None = None
        self._server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._server.serve())

    def stop(self) -> None:
        self._server.should_exit = True
        if self.loop is not None:
            self.loop.call_soon_threadsafe(lambda: setattr(self._server, "should_exit", True))


async def _login(http: httpx.AsyncClient, email: str, password: str) -> str:
    resp = await http.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


async def _create_bot(http: httpx.AsyncClient, token: str, strategy: str = "fake_strategy") -> int:
    headers = {"Authorization": f"Bearer {token}"}
    resp = await http.post(
        "/bots",
        headers=headers,
        json={"name": "A", "strategy": strategy, "is_paper": True},
    )
    assert resp.status_code == 201, f"Create bot failed: {resp.text}"
    return resp.json()["id"]


async def _start_bot(http: httpx.AsyncClient, token: str, bot_id: int) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    resp = await http.post(f"/bots/{bot_id}/start", headers=headers, json={})
    assert resp.status_code == 200, f"Start bot failed: {resp.text}"
    return resp.json()


async def _recv_until(ws, msg_type: str, timeout: float = 5.0) -> dict:
    """Receives messages until one of the given type arrives."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout)
        msg = json.loads(raw)
        if msg.get("type") == msg_type:
            return msg


async def _publish_on_loop(loop, event_type: str, data: dict) -> None:
    """Publishes an event on the uvicorn event loop (from the test loop)."""

    async def _p() -> None:
        get_event_bus().publish(event_type, data)

    await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(_p(), loop))


@pytest.fixture
async def ws_env():
    """App con routers de auth/bots/risk/ws corriendo bajo uvicorn."""
    import src.core.services.bot_manager as bm_module
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.adapters.database.session import get_db
    from src.api.limiter import limiter
    from src.api.routes.auth_routes import router as auth_router
    from src.api.routes.bot_routes import router as bot_router
    from src.api.routes.risk_routes import router as risk_router
    from src.api.routes.ws_routes import router as ws_router
    from src.core.services.auth_service import auth_service

    clear_event_bus()
    clear_ws_manager()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(engine, expire_on_commit=False)
    auth_service._session_factory = test_factory

    # Patch del singleton del BotManager para usar la DB y el factory de test
    bm_module._bot_manager_instance = BotManager(
        session_factory=test_factory,
        adapter_factory=FakeAdapterFactory(),
    )

    # Registrar una estrategia determinista para que los bots tengan executor
    strategy_manager._registry["fake_strategy"] = FakeStrategy

    await auth_service.create_user(USER1_EMAIL, USER_PASSWORD, role="user")
    await auth_service.create_user(USER2_EMAIL, USER_PASSWORD, role="user")

    limiter.reset()

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)
    app.include_router(bot_router)
    app.include_router(risk_router)
    app.include_router(ws_router)

    async def _override_db():
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    port = _free_port()
    thread = _ServerThread(app, port)
    thread.start()
    _wait_for_server(port)

    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as http:
        yield http, thread, port

    thread.stop()
    thread.join(timeout=5)
    await engine.dispose()


class TestWsBots:
    """Tests del endpoint WebSocket /ws/bots."""

    async def test_connect_with_valid_token(self, ws_env):
        """Con un JWT válido se conecta y recibe el estado inicial."""
        http, _, port = ws_env
        token = await _login(http, USER1_EMAIL, USER_PASSWORD)
        bot_id = await _create_bot(http, token)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/bots?token={token}"
        ) as ws:
            msg = await _recv_until(ws, "initial_state")
            assert any(
                b["bot_id"] == bot_id and b["status"] == "stopped" for b in msg["bots"]
            )

    async def test_connect_with_invalid_token(self, ws_env):
        """Con un token inválido se rechaza la conexión."""
        _, _, port = ws_env
        with pytest.raises(websockets.exceptions.WebSocketException):
            await websockets.connect(_ws_url(port, "not-a-jwt"))

    async def test_receive_bot_status_update(self, ws_env):
        """Al arrancar un bot se recibe una actualización de estado por WS."""
        http, _, port = ws_env
        token = await _login(http, USER1_EMAIL, USER_PASSWORD)
        bot_id = await _create_bot(http, token)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/bots?token={token}"
        ) as ws:
            await _recv_until(ws, "initial_state")
            await _start_bot(http, token, bot_id)
            msg = await _recv_until(ws, "bot_status")
            assert msg["bot_id"] == bot_id
            assert msg["status"] == "running"

    async def test_receive_trade_update(self, ws_env):
        """Al ejecutarse un trade se recibe una actualización de trade por WS."""
        http, _, port = ws_env
        token = await _login(http, USER1_EMAIL, USER_PASSWORD)
        bot_id = await _create_bot(http, token)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/bots?token={token}"
        ) as ws:
            await _recv_until(ws, "initial_state")
            await _start_bot(http, token, bot_id)
            msg = await _recv_until(ws, "trade")
            assert msg["bot_id"] == bot_id
            assert msg["trade"]["side"] == "buy"
            assert msg["trade"]["symbol"] == "BTC-USD"

    async def test_receive_risk_update(self, ws_env):
        """Al registrarse un trade se recibe una actualización de riesgo por WS."""
        http, _, port = ws_env
        token = await _login(http, USER1_EMAIL, USER_PASSWORD)
        bot_id = await _create_bot(http, token)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/bots?token={token}"
        ) as ws:
            await _recv_until(ws, "initial_state")
            await _start_bot(http, token, bot_id)
            msg = await _recv_until(ws, "risk_update")
            assert msg["bot_id"] == bot_id
            assert "current_balance" in msg["status"]

    async def test_ping_pong(self, ws_env):
        """Al enviar un ping se recibe un pong."""
        http, _, port = ws_env
        token = await _login(http, USER1_EMAIL, USER_PASSWORD)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/bots?token={token}"
        ) as ws:
            await _recv_until(ws, "initial_state")
            await ws.send(json.dumps({"type": "ping"}))
            msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert msg["type"] == "pong"

    async def test_subscribe_specific_bot(self, ws_env):
        """Tras suscribirse a un bot, solo se reciben sus actualizaciones."""
        http, thread, port = ws_env
        token = await _login(http, USER1_EMAIL, USER_PASSWORD)
        bot1 = await _create_bot(http, token)
        bot2 = await _create_bot(http, token)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/bots?token={token}"
        ) as ws:
            await _recv_until(ws, "initial_state")
            await ws.send(json.dumps({"type": "subscribe", "bot_id": bot1}))
            # Esperar a que el servidor procese la suscripción.
            await asyncio.sleep(0.2)
            # Publicar eventos para ambos bots; solo bot1 debe llegar.
            await _publish_on_loop(
                thread.loop,
                "bot.status_changed",
                {"user_id": 1, "bot_id": bot2, "status": "running"},
            )
            await _publish_on_loop(
                thread.loop,
                "bot.status_changed",
                {"user_id": 1, "bot_id": bot1, "status": "running"},
            )
            msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert msg["type"] == "bot_status"
            assert msg["bot_id"] == bot1
            # El evento de bot2 fue filtrado; no deben llegar más mensajes.
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws.recv(), 0.5)

    async def test_disconnect_cleanup(self, ws_env):
        """Al desconectarse, la conexión se elimina del manager."""
        http, _, port = ws_env
        token = await _login(http, USER1_EMAIL, USER_PASSWORD)
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/bots?token={token}"
        ) as ws:
            await _recv_until(ws, "initial_state")
            assert 1 in get_ws_manager().active_connections
        # Tras cerrar, la conexión debe limpiarse.
        deadline = time.time() + 3
        while time.time() < deadline and 1 in get_ws_manager().active_connections:
            await asyncio.sleep(0.05)
        assert 1 not in get_ws_manager().active_connections

    async def test_unauthorized_user_does_not_receive_other_users_bots(self, ws_env):
        """El usuario A no recibe actualizaciones de los bots del usuario B."""
        http, thread, port = ws_env
        token1 = await _login(http, USER1_EMAIL, USER_PASSWORD)
        token2 = await _login(http, USER2_EMAIL, USER_PASSWORD)
        bot1 = await _create_bot(http, token1)
        async with websockets.connect(_ws_url(port, token1)) as ws1, websockets.connect(
            _ws_url(port, token2)
        ) as ws2:
            await _recv_until(ws1, "initial_state")
            await _recv_until(ws2, "initial_state")
            await _publish_on_loop(
                thread.loop,
                "bot.status_changed",
                {"user_id": 1, "bot_id": bot1, "status": "running"},
            )
            # user1 recibe el evento.
            msg = json.loads(await asyncio.wait_for(ws1.recv(), 5))
            assert msg["type"] == "bot_status"
            assert msg["bot_id"] == bot1
            # user2 no lo recibe.
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws2.recv(), 0.5)
