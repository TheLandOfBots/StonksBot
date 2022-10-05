import os
from dotenv import load_dotenv
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
import datetime
from datetime import timedelta
from iex_cloud_api import IEXCloudAPI, IEXCloudAPIError

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

iex_cloud_api = IEXCloudAPI(os.getenv("IEX_CLOUD_TOKEN", ""))


async def run_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message."""
    job = context.job
    await context.bot.send_message(
        job.chat_id, text=f"Job: {job.data}, user: {context.user_data}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot")


async def track_stonks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    portfolio = context.user_data.get("portfolio", {})
    ticker = context.args[0]
    amount = float(context.args[1])
    buy_price = float(context.args[2])

    if ticker in portfolio:
        old_state = portfolio[ticker]
        new_amount = old_state["amount"] + amount
        new_buy_price = (
            (old_state["amount"] * old_state["buy_price"]) + (amount * buy_price)
        ) / new_amount

        portfolio[ticker] = {"amount": new_amount, "buy_price": new_buy_price}
    else:
        portfolio[ticker] = {"amount": amount, "buy_price": buy_price}

    context.user_data["portfolio"] = portfolio
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=str(portfolio)
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

    for ticker in portfolio:
        try:
            current_price = iex_cloud_api.get_stock_price(ticker)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{ticker}: ${current_price}",
            )
        except IEXCloudAPIError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Failed to retrieve price for {ticker}",
            )


async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_message.chat_id

    # -2 hours
    # premarket_time = datetime.time(hour=17, minute=51)
    # aftermarket_time = datetime.time(15, 56, 00)

    premarket_time = (datetime.datetime.utcnow() + timedelta(seconds=5)).time()
    aftermarket_time = (datetime.datetime.utcnow() + timedelta(seconds=10)).time()

    context.job_queue.run_daily(
        run_job,
        premarket_time,
        chat_id=chat_id,
        user_id=chat_id,
        name=str(chat_id),
    )

    context.job_queue.run_daily(
        run_job,
        aftermarket_time,
        chat_id=chat_id,
        user_id=chat_id,
        name=str(chat_id),
    )

    await context.bot.send_message(chat_id=chat_id, text="Notifications activated")


async def disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_message.chat_id

    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if jobs:
        for job in jobs:
            job.schedule_removal()

    await context.bot.send_message(chat_id=chat_id, text="Notifications disabled!")


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
