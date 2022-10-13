from typing import Optional, Tuple
from stock_data import StockData


def calculate_movements(
    prev_data: StockData, current_price: float
) -> Tuple[Optional[float], Optional[float], float, float]:
    prev_price = prev_data.last_price
    day_movement = None
    day_movement_pct = None

    if prev_price:
        # calculate day price movement
        day_movement = round(current_price - prev_price, 2)
        day_movement_pct = round((day_movement / prev_price) * 100, 2)

    # calculate total price movement
    buy_price = prev_data.buy_price
    movement = current_price - buy_price
    total_movement = round(movement * prev_data.amount, 2)
    total_movement_pct = round((movement / buy_price) * 100, 2)

    return day_movement, day_movement_pct, total_movement, total_movement_pct


def format_ticker_message(
    ticker: str,
    current_price: float,
    day_movement: Optional[float],
    day_movement_pct: Optional[float],
    total_movement: float,
    total_movement_pct: float,
) -> str:
    message = f"*{ticker}*: ${current_price}"
    if day_movement is not None and day_movement_pct is not None:
        message += " D:(${:+.2f}/{:+.2f}%)".format(
            day_movement, day_movement_pct
        )

    message += " T:(${:+.2f}/{:+.2f}%)".format(
        total_movement, total_movement_pct
    )

    return message
