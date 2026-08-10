import logging
from typing import Any

from src.core.ports.i_strategy import IStrategy

logger = logging.getLogger(__name__)


class BaseStrategy(IStrategy):
    """Clase base opcional que incluye helpers para indicadores."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = logger

    # Aquí podrías añadir métodos utilitarios como RSI, EMA, etc.
    # para que las estrategias hijas los hereden y no repitan código.

    # Las estrategias concretas deben implementar 'analyze' y 'get_required_params'.
