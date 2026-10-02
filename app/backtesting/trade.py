from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    timestamp: datetime
    direction: str

    entry_price: float
    stop_loss: float
    take_profit: float

    exit_price: float | None = None
    exit_timestamp: datetime | None = None

    result: str | None = None
    profit: float = 0.0