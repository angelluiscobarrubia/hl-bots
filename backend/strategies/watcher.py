"""Watcher de la carpeta ``strategies/`` para hot-reload.

Usa ``watchfiles`` (asyncio nativo) para detectar cambios en disco y
disparar :meth:`StrategyManager.reload`. Diseñado para correr como tarea
background dentro del event loop de FastAPI.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from pathlib import Path

from src.core.logging import get_logger
from watchfiles import awatch

logger = get_logger(__name__)

_STRATEGIES_DIR = Path(__file__).resolve().parent


class StrategiesWatcher:
    """Observa ``strategies/`` y llama a un callback en cada cambio."""

    def __init__(
        self,
        on_change: Callable[[], Awaitable[None]],
        debounce_seconds: float = 0.5,
    ) -> None:
        self._on_change = on_change
        self._debounce = debounce_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def _run(self) -> None:
        logger.info("strategies_watcher.start", path=str(_STRATEGIES_DIR))
        try:
            async for changes in awatch(_STRATEGIES_DIR):
                if self._stop_event.is_set():
                    break
                logger.info("strategies_watcher.changes", changes=changes)
                # Debounce: si llega otro evento, el await se alarga.
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._debounce,
                    )
                if self._stop_event.is_set():
                    break
                try:
                    await self._on_change()
                except Exception:
                    logger.exception("strategies_watcher.callback_failed")
        finally:
            logger.info("strategies_watcher.stopped")

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="strategies-watcher")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except TimeoutError:
                self._task.cancel()
            self._task = None
