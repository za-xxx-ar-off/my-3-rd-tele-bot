import os
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== ENV =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))

# ===== BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает через webhook ✅")

# Создаем приложение бота
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# Инициализация бота один раз (не для каждого запроса!)
asyncio.run(application.initialize())
asyncio.run(application.start())

# ===== FLASK =====
flask_app = Flask(__name__)

@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Обработка входящих обновлений от Telegram через webhook"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    # Вызываем асинхронную обработку update в синхронном контексте
    asyncio.run(application.process_update(update))
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
