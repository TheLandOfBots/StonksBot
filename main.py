import os
from dotenv import load_dotenv
import logging
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
import datetime
from bot_application import BotApplication
from iex_cloud_api import IEXCloudAPI, IEXCloudAPIError
from stock_data import StockData
from utils import calculate_movements, format_ticker_message


async def send_stonks_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    portfolio = context.user_data.get("portfolio", {})
    assert isinstance(
        context.application, BotApplication
    ), "Application must be an instance of BotApplication!"

    if len(portfolio) == 0:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Your portfolio is empty!",
        )
        return

    message = ""
    for ticker in portfolio:
        try:
            current_price = (
                context.application.iex_cloud_api_client.get_stock_price(
                    ticker
                )
            )
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

    try:
        ticker = context.args[0]
        amount = float(context.args[1])
        buy_price = float(context.args[2])
    except (ValueError, IndexError):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Invalid format, please use /track <STOCK_TICKER> <QUANTITY> <BUY_PRICE> (e.g. /track TSLA 10.5 235.5)",
        )
        return

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
    assert isinstance(
        context.application, BotApplication
    ), "Application must be an instance of BotApplication!"

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
            current_price = (
                context.application.iex_cloud_api_client.get_stock_price(
                    ticker
                )
            )
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
    # UTC open time 13:30 + 30 min delay
    premarket_time = datetime.time(hour=14, minute=0)
    # UTC close time 20:00 + 30 min delay
    aftermarket_time = datetime.time(hour=20, minute=30)

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
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    load_dotenv()
    persistence = PicklePersistence(filepath="stonks_bot_data.pkl")
    iex_cloud_api = IEXCloudAPI(os.getenv("IEX_CLOUD_TOKEN", ""))
    application = (
        ApplicationBuilder()
        .application_class(
            BotApplication, kwargs={"iex_cloud_api_client": iex_cloud_api}
        )
        .token(os.getenv("TOKEN", ""))
        .persistence(persistence)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("track", track_stonks))
    application.add_handler(CommandHandler("portfolio", show_portfolio))
    application.add_handler(CommandHandler("notify", notify))
    application.add_handler(CommandHandler("disable", disable))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    application.run_polling()
