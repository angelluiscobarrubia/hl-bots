"""Event bus for internal domain events.

Provides a lightweight publish/subscribe mechanism so services can emit domain
events (bot started, trade executed, risk updated, ...) without depending on
the WebSocket layer directly. The WebSocket layer subscribes to these events
and forwards them to connected clients.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)

# Event types emitted by the domain services.
EVENT_BOT_STATUS_CHANGED = "bot.status_changed"
EVENT_BOT_TRADE_EXECUTED = "bot.trade_executed"
EVENT_BOT_RISK_UPDATED = "bot.risk_updated"
EVENT_BOT_RISK_HALTED = "bot.risk_halted"

Handler = Callable[[dict[str, Any]], Any]


class EventBus:
    """Publish/subscribe bus for internal domain events."""

    def __init__(self) -> None:
        self.subscribers: dict[str, list[Handler]] = {}

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Registers a handler for an event type."""
        self.subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        """Removes a previously registered handler."""
        handlers = self.subscribers.get(event_type)
        if handlers is None:
            return
        if handler in handlers:
            handlers.remove(handler)
        if not handlers:
            self.subscribers.pop(event_type, None)

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Fires an event to all registered handlers.

        Async handlers are scheduled on the current event loop (or run in a
        fresh loop if none is running) so sync callers can publish safely.
        """
        for handler in list(self.subscribers.get(event_type, [])):
            try:
                result = handler(data)
                if inspect.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop is not None:
                        loop.create_task(result)
                    else:
                        asyncio.run(result)
            except Exception:
                logger.exception("event_bus.handler_failed", event_type=event_type)


# Singleton lazy: no falla al importar si la DB no está configurada.
_event_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """Devuelve el singleton del EventBus, creándolo lazily."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance


def clear_event_bus() -> None:
    """Resetea el singleton del EventBus (principalmente para tests)."""
    global _event_bus_instance
    _event_bus_instance = None
