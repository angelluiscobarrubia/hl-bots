from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BotStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class Bot(BaseModel):
    id: str
    user_id: str
    name: str
    strategy_name: str  # Coincide con el nombre del plugin
    symbol: str = "BTC-USD"
    is_paper: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    status: BotStatus = BotStatus.STOPPED
