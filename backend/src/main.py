"""Punto de entrada de la API FastAPI.

Arranca logging estructurado, instrumentación Prometheus y el watcher
de estrategias para hot-reload.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from strategies.watcher import StrategiesWatcher

from src.api.limiter import limiter
from src.api.routes import (
    admin_routes,
    api_key_routes,
    auth_routes,
    bot_routes,
    risk_routes,
)
from src.core.logging import configure_logging, get_logger
from src.core.services.strategy_manager import strategy_manager

# uvloop en Linux/macOS para ~2x throughput. Debe activarse antes de crear
# el event loop (antes de importar uvicorn.run).
if sys.platform != "win32":
    try:
        import uvloop as _uvloop  # type: ignore[import-untyped]

        asyncio.set_event_loop_policy(_uvloop.EventLoopPolicy())
    except ImportError:
        pass

# Inicialización temprana del logging antes de crear la app
configure_logging()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga inicial + arranque del watcher de strategies."""
    logger.info("startup.begin")

    strategy_manager.reload()

    async def _on_strategy_change() -> None:
        strategy_manager.reload()

    watcher = StrategiesWatcher(on_change=_on_strategy_change)
    watcher.start()
    app.state.strategies_watcher = watcher

    logger.info("startup.ready", strategies=strategy_manager.available)
    try:
        yield
    finally:
        logger.info("shutdown.begin")
        await watcher.stop()
        logger.info("shutdown.done")


app = FastAPI(
    title="Hyperliquid Bot Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Routers de autenticación y administración
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(api_key_routes.router)
app.include_router(bot_routes.router)
app.include_router(risk_routes.router)

# Métricas Prometheus en /metrics
Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "hyperliquid-bot-platform",
        "version": "0.1.0",
        "strategies_available": strategy_manager.available,
    }


@app.get("/strategies")
async def list_strategies():
    """Lista estrategias registradas (para la UI)."""
    return {
        "available": strategy_manager.available,
        "count": len(strategy_manager.available),
    }


@app.post("/strategies/reload")
async def reload_strategies():
    """Fuerza un reload del StrategyManager (útil para debug)."""
    registered = strategy_manager.reload()
    return {"registered": list(registered), "count": len(registered)}
