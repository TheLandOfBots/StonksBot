from dataclasses import dataclass
from typing import Optional


@dataclass
class StockData:
    amount: float
    buy_price: float
    last_price: Optional[float]
