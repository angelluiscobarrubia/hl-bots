"""Plugins de estrategias de trading (cargados dinámicamente).

Para añadir una nueva estrategia:
1. Crea un archivo .py aquí (ej. ``my_strategy.py``).
2. Define una clase que herede de :class:`base_strategy.BaseStrategy`.
3. Implementa ``analyze`` y ``get_required_params``.
4. El :class:`src.core.services.strategy_manager.StrategyManager` la detectará
   automáticamente (al reiniciar el manager; los bots activos siguen con la
   instancia anterior hasta que se reinicien manualmente).
"""

import os as _os
import sys as _sys

# Bootstrap de paths: ``strategies/`` y ``backend/src/`` deben estar en
# ``sys.path`` para que los módulos del paquete se importen entre sí
# (``from base_strategy import BaseStrategy``) y para que los imports absolutos
# ``from src.X import Y`` resuelvan correctamente cuando ``StrategyManager``
# carga estos archivos de forma dinámica (sin pasar por el paquete
# ``src.main`` que sí conoce el path).
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_BACKEND_ROOT = _os.path.dirname(_HERE)
_SRC_DIR = _os.path.join(_BACKEND_ROOT, "src")

for _p in (_SRC_DIR, _HERE):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from base_strategy import BaseStrategy  # noqa: E402

__all__ = ["BaseStrategy"]
