import os
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ========= ENV =========
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))

# ========= BOT =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен ✅")

application: Application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# ========= FLASK =========
flask_app = Flask(__name__)

@flask_app.post(f"/{TELEGRAM_TOKEN}")
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "OK"

@flask_app.get("/")
def health():
    return "OK", 200

# ========= START =========
if __name__ == "__main__":
    asyncio.run(application.initialize())
    asyncio.run(application.start())
    flask_app.run(host="0.0.0.0", port=PORT)
