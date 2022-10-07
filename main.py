import os
from dotenv import load_dotenv
import logging
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
import datetime
from dataclasses import dataclass
from datetime import timedelta
from iex_cloud_api import IEXCloudAPI, IEXCloudAPIError
from typing import Optional, Tuple

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

iex_cloud_api = IEXCloudAPI(os.getenv("IEX_CLOUD_TOKEN", ""))


@dataclass
class StockData:
    amount: float
    buy_price: float
    last_price: Optional[float]


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

        # make sure the percentage has a correct sign
        if day_movement < 0:
            day_movement_pct = -day_movement_pct

    # calculate total price movement
    buy_price = prev_data.buy_price
    total_movement = round((current_price - buy_price) * prev_data.amount, 2)
    total_movement_pct = round((total_movement / buy_price) * 100, 2)

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


async def send_stonks_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    portfolio = context.user_data.get("portfolio", {})

    if len(portfolio) == 0:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Your portfolio is empty!",
        )
        return

    message = ""
    for ticker in portfolio:
        try:
            current_price = iex_cloud_api.get_stock_price(ticker)
        except IEXCloudAPIError:
            portfolio[ticker].last_price = None
            message += f"*{ticker}*: Failed to retrieve price\n"
        else:
            (
                day_movement,
                day_movement_pct,
                total_movement,
                total_movement_pct,
            ) = calculate_movements(portfolio[ticker], current_price)
            message += format_ticker_message(
                ticker,
                current_price,
                day_movement,
                day_movement_pct,
                total_movement,
                total_movement_pct,
            )
            message += "\n"
            portfolio[ticker].last_price = current_price

    await context.bot.send_message(
        chat_id=chat_id, text=message, parse_mode=constants.ParseMode.MARKDOWN
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Stonks!"
    )


async def track_stonks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    portfolio = context.user_data.get("portfolio", {})

    # TODO: validate
    ticker = context.args[0]
    amount = float(context.args[1])
    buy_price = float(context.args[2])

    if ticker in portfolio:
        # calculate new state
        data = portfolio[ticker]
        new_amount = data.amount + amount
        new_buy_price = (
            (data.amount * data.buy_price) + (amount * buy_price)
        ) / new_amount

        # update record
        data.amount = new_amount
        data.buy_price = new_buy_price
    else:
        portfolio[ticker] = StockData(amount, buy_price, None)

    context.user_data["portfolio"] = portfolio

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Gotcha!"
    )


async def show_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data or {}
    portfolio = user_data.get("portfolio", {})
    if len(portfolio) == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Your portfolio is empty!",
        )
        return

    message = ""
    for ticker in portfolio:
        try:
            current_price = iex_cloud_api.get_stock_price(ticker)
        except IEXCloudAPIError:
            message += f"*{ticker}*: Failed to retrieve price\n"
        else:
            (
                day_movement,
                day_movement_pct,
                total_movement,
                total_movement_pct,
            ) = calculate_movements(portfolio[ticker], current_price)
            message += format_ticker_message(
                ticker,
                current_price,
                day_movement,
                day_movement_pct,
                total_movement,
                total_movement_pct,
            )
            message += "\n"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_message.chat_id

    # -2 hours
    # premarket_time = datetime.time(hour=17, minute=51)
    # aftermarket_time = datetime.time(15, 56, 00)

    premarket_time = (datetime.datetime.utcnow() + timedelta(seconds=5)).time()
    aftermarket_time = (
        datetime.datetime.utcnow() + timedelta(seconds=10)
    ).time()

    context.job_queue.run_daily(
        send_stonks_update,
        premarket_time,
        chat_id=chat_id,
        user_id=chat_id,
        name=str(chat_id),
    )

    context.job_queue.run_daily(
        send_stonks_update,
        aftermarket_time,
        chat_id=chat_id,
        user_id=chat_id,
        name=str(chat_id),
    )

    await context.bot.send_message(
        chat_id=chat_id, text="Notifications activated"
    )


async def disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_message.chat_id

    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        for job in jobs:
            job.schedule_removal()

    await context.bot.send_message(
        chat_id=chat_id, text="Notifications disabled!"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_message.chat_id

    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        message = "Notifications are enabled"
    else:
        message = "Notofications are disabled"
    await context.bot.send_message(chat_id=chat_id, text=message)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Unknown command: {update.message.text}",
    )


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.getenv("TOKEN", "")).build()

    start_handler = CommandHandler("start", start)
    track_handler = CommandHandler("track", track_stonks)
    portfolio_handler = CommandHandler("portfolio", show_portfolio)
    notify_handler = CommandHandler("notify", notify)
    disable_handler = CommandHandler("disable", disable)
    status_handler = CommandHandler("status", status)

    application.add_handler(start_handler)
    application.add_handler(track_handler)
    application.add_handler(portfolio_handler)
    application.add_handler(notify_handler)
    application.add_handler(disable_handler)
    application.add_handler(status_handler)
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)

    application.run_polling()
