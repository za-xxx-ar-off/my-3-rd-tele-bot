import os
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ========= ENV =========
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))

# ========= BOT =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает через webhook ✅")

# ========= APPLICATION =========
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# 🔑 создаём event loop ОДИН РАЗ
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())
loop.run_until_complete(application.start())

# ========= FLASK =========
flask_app = Flask(__name__)

@flask_app.post(f"/{TELEGRAM_TOKEN}")
def telegram_webhook():
    update = Update.de_json(
        request.get_json(force=True),
        application.bot
    )
    loop.create_task(application.process_update(update))
    return "OK", 200

@flask_app.get("/")
def health():
    return "OK", 200
