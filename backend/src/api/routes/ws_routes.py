"""WebSocket routes for live bot updates.

Authenticates the connection via a JWT ``?token=`` query parameter, registers
it with the :class:`ConnectionManager`, sends the user's current bot state and
then pushes live updates (status changes, trades, risk metrics) as they are
published on the :class:`EventBus`.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.adapters.security.jwt import decode_token
from src.core.logging import get_logger
from src.core.services.bot_manager import get_bot_manager
from src.core.services.event_bus import (
    EVENT_BOT_RISK_HALTED,
    EVENT_BOT_RISK_UPDATED,
    EVENT_BOT_STATUS_CHANGED,
    EVENT_BOT_TRADE_EXECUTED,
    get_event_bus,
)
from src.core.services.ws_manager import get_ws_manager

logger = get_logger(__name__)

router = APIRouter()

# Maps an EventBus event type to the WebSocket message type it produces.
_EVENT_TO_MESSAGE: dict[str, str] = {
    EVENT_BOT_STATUS_CHANGED: "bot_status",
    EVENT_BOT_TRADE_EXECUTED: "trade",
    EVENT_BOT_RISK_UPDATED: "risk_update",
    EVENT_BOT_RISK_HALTED: "risk_halt",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _authenticate(websocket: WebSocket) -> int | None:
    """Validates the JWT token and returns the user id, or None if invalid."""
    params = websocket.query_params
    token = params["token"] if "token" in params else None  # noqa: SIM401
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None


def _build_message(msg_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Builds a server->client message from an event payload."""
    message: dict[str, Any] = {
        "type": msg_type,
        "bot_id": data.get("bot_id"),
        "timestamp": _iso_now(),
    }
    if msg_type == "bot_status":
        message["status"] = data.get("status")
    elif msg_type == "trade":
        message["trade"] = data.get("trade")
    elif msg_type == "risk_update":
        message["status"] = data.get("status")
    elif msg_type == "risk_halt":
        message["reason"] = data.get("reason")
    return message


def _make_event_handler(
    websocket: WebSocket,
    user_id: int,
    subscribed: set[int],
    msg_type: str,
) -> Any:
    """Builds an async handler that filters events for the connection."""

    async def handler(data: dict[str, Any]) -> None:
        if data.get("user_id") != user_id:
            return
        bot_id = data.get("bot_id")
        if subscribed and bot_id is not None and bot_id not in subscribed:
            return
        await websocket.send_json(_build_message(msg_type, data))

    return handler


async def _send_initial_state(websocket: WebSocket, user_id: int) -> None:
    """Sends the user's current bots with their status."""
    bots = await get_bot_manager().list_bot_models(user_id)
    await websocket.send_json(
        {
            "type": "initial_state",
            "bots": [{"bot_id": b.id, "status": b.status} for b in bots],
        }
    )


async def _handle_client_message(
    websocket: WebSocket,
    subscribed: set[int],
    raw: str,
) -> None:
    """Processes a client->server message (ping / subscribe / unsubscribe)."""
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return
    msg_type = message.get("type")
    if msg_type == "ping":
        await websocket.send_json({"type": "pong", "timestamp": _iso_now()})
    elif msg_type == "subscribe":
        bot_id = message.get("bot_id")
        if bot_id is not None:
            with contextlib.suppress(TypeError, ValueError):
                subscribed.add(int(bot_id))
    elif msg_type == "unsubscribe":
        bot_id = message.get("bot_id")
        if bot_id is not None:
            with contextlib.suppress(TypeError, ValueError):
                subscribed.discard(int(bot_id))


@router.websocket("/ws/bots")
async def ws_bots(websocket: WebSocket) -> None:
    """Live bot updates endpoint."""
    user_id = await _authenticate(websocket)
    if user_id is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    manager = get_ws_manager()
    event_bus = get_event_bus()
    manager.connect(websocket, user_id)

    subscribed: set[int] = set()
    handlers = {
        event_type: _make_event_handler(websocket, user_id, subscribed, msg_type)
        for event_type, msg_type in _EVENT_TO_MESSAGE.items()
    }
    for event_type, handler in handlers.items():
        event_bus.subscribe(event_type, handler)

    try:
        await _send_initial_state(websocket, user_id)
        while True:
            raw = await websocket.receive_text()
            await _handle_client_message(websocket, subscribed, raw)
    except WebSocketDisconnect:
        logger.info("ws_bots.disconnected", user_id=user_id)
    except Exception:
        logger.exception("ws_bots.error", user_id=user_id)
    finally:
        for event_type, handler in handlers.items():
            event_bus.unsubscribe(event_type, handler)
        manager.disconnect(websocket, user_id)
