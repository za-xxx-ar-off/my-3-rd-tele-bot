import os
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ================== ENV ==================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))

# ================== BOT ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на команду /start"""
    await update.message.reply_text("Бот работает через webhook ✅")

# ================== APPLICATION ==================
# Создаем приложение бота
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# 🔑 Создаем event loop и инициализируем приложение
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())
loop.run_until_complete(application.start())

# ================== FLASK ==================
flask_app = Flask(__name__)

# Webhook route для Telegram
@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Обработка входящих обновлений от Telegram через webhook"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    # Используем create_task, чтобы не блокировать Flask
    application.create_task(application.process_update(update))
    return "OK", 200

# Простая проверка работоспособности
@flask_app.route("/", methods=["GET"])
def health():
    return "OK", 200

# ================== RUN ==================
if __name__ == "__main__":
    # Flask будет слушать порт Render
    flask_app.run(host="0.0.0.0", port=PORT)
