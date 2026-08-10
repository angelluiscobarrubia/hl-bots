from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Order(BaseModel):
    id: str
    bot_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = datetime.utcnow()
    filled_at: datetime | None = None
    error_msg: str | None = None
