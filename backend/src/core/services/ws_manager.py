"""WebSocket connection manager.

Tracks active WebSocket connections per user so the API can push live updates
(bot status, trades, risk metrics) without polling.
"""

from __future__ import annotations

from fastapi import WebSocket
from src.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Tracks active WebSocket connections grouped by user."""

    def __init__(self) -> None:
        self.active_connections: dict[int, set[WebSocket]] = {}

    def connect(self, websocket: WebSocket, user_id: int) -> None:
        """Stores a new connection for the user."""
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        """Removes a connection, cleaning up empty user buckets."""
        connections = self.active_connections.get(user_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_personal(self, message: dict, user_id: int) -> None:
        """Sends a message to all connections of a user."""
        for websocket in list(self.active_connections.get(user_id, set())):
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning(
                    "ws_manager.send_personal_failed", user_id=user_id, exc_info=True
                )

    async def broadcast(self, message: dict) -> None:
        """Sends a message to every active connection (admin use)."""
        for connections in list(self.active_connections.values()):
            for websocket in list(connections):
                try:
                    await websocket.send_json(message)
                except Exception:
                    logger.warning("ws_manager.broadcast_failed", exc_info=True)


# Singleton lazy: no falla al importar si la DB no está configurada.
_ws_manager_instance: ConnectionManager | None = None


def get_ws_manager() -> ConnectionManager:
    """Devuelve el singleton del ConnectionManager, creándolo lazily."""
    global _ws_manager_instance
    if _ws_manager_instance is None:
        _ws_manager_instance = ConnectionManager()
    return _ws_manager_instance


def clear_ws_manager() -> None:
    """Resetea el singleton del ConnectionManager (principalmente para tests)."""
    global _ws_manager_instance
    _ws_manager_instance = None
