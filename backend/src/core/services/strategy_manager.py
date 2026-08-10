"""StrategyManager: registro y carga dinámica de estrategias.

Escanea ``backend/strategies/`` y registra toda clase que herede de
:class:`strategies.BaseStrategy`. Las estrategias activas NO se recargan
automáticamente; el operador debe reiniciar el bot manualmente.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)

_STRATEGIES_PACKAGE = "strategies"
_BASE_CLASS_NAME = "BaseStrategy"


class StrategyManager:
    """Registro singleton de estrategias disponibles."""

    def __init__(self) -> None:
        self._registry: dict[str, type[Any]] = {}

    def reload(self) -> dict[str, type[Any]]:
        """Reescanea el paquete ``strategies`` y devuelve el registro actualizado.

        Las instancias activas de bots siguen usando las clases anteriores
        (Python no puede "reemplazar" el tipo de un objeto ya creado). Para
        aplicar cambios el operador debe reiniciar el bot desde la UI.
        """
        logger.info("strategy_manager.reload.start", package=_STRATEGIES_PACKAGE)
        self._registry.clear()

        # Forzar reimports para que edit-and-save sea visible
        for mod_name in list(sys.modules):
            if mod_name == _STRATEGIES_PACKAGE or mod_name.startswith(
                f"{_STRATEGIES_PACKAGE}.",
            ):
                del sys.modules[mod_name]

        strategies_path = Path(__file__).resolve().parents[3] / _STRATEGIES_PACKAGE

        for _finder, name, _is_pkg in pkgutil.iter_modules([str(strategies_path)]):
            if name.startswith("_"):
                continue
            full_name = f"{_STRATEGIES_PACKAGE}.{name}"
            try:
                module = importlib.import_module(full_name)
            except Exception:
                logger.exception("strategy_manager.import_failed", module=full_name)
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name, None)
                if (
                    isinstance(attr, type)
                    and attr_name != _BASE_CLASS_NAME
                    and self._is_strategy(attr)
                ):
                    self._registry[attr_name] = attr
                    logger.info(
                        "strategy_manager.registered",
                        strategy=attr_name,
                        module=full_name,
                    )

        logger.info(
            "strategy_manager.reload.done",
            count=len(self._registry),
            names=sorted(self._registry),
        )
        return dict(self._registry)

    @staticmethod
    def _is_strategy(cls: type) -> bool:
        try:
            from base_strategy import BaseStrategy as _Base

            return issubclass(cls, _Base)
        except Exception:
            return False

    @property
    def available(self) -> list[str]:
        return sorted(self._registry)

    def get(self, name: str) -> type[Any]:
        if name not in self._registry:
            raise KeyError(
                f"Estrategia '{name}' no registrada. Disponibles: {self.available}",
            )
        return self._registry[name]


# Singleton a nivel de módulo
strategy_manager = StrategyManager()
