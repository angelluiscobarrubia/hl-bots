"""Logging estructurado con ``structlog``.

Configura tanto ``structlog`` como el logger estándar de la stdlib para que
todas las librerías (uvicorn, sqlalchemy, alembic) emitan logs consistentes.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from src.core.config import settings


def _add_app_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inyecta app_env y versión en cada log."""
    event_dict.setdefault("app_env", settings.app_env)
    return event_dict


def configure_logging() -> None:
    """Configura structlog + stdlib logging. Idempotente."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _add_app_context,
    ]

    if settings.app_env == "development":
        renderer: Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    # Structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Stdlib root logger
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Subir nivel de librerías ruidosas
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Helper para obtener un logger pre-configurado."""
    return structlog.get_logger(name)
