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

# Google Sheets (заготовка)
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
SHEET_NAME = os.environ.get("SHEET_NAME")

# ========= BOT HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает через webhook ✅")

# ========= APPLICATION =========
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# 🔑 создаём event loop один раз
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())
loop.run_until_complete(application.start())

# ========= FLASK =========
flask_app = Flask(__name__)

@flask_app.post(f"/{TELEGRAM_TOKEN}")
def telegram_webhook():
    """Webhook для Telegram"""
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        loop.run_until_complete(application.process_update(update))  # ждём обработки
        return "OK", 200
    except Exception as e:
        print("Webhook error:", e)
        return "Internal Server Error", 500

@flask_app.get("/")
def health():
    """Проверка, что сервис жив"""
    return "OK", 200

# ========= MAIN =========
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
