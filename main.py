import os
import json
import asyncio
import logging

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import gspread
from google.oauth2.service_account import Credentials

# -------------------------------------------------
# Логи
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# ENV
# -------------------------------------------------
BOT_TOKEN = os.environ["BOT_TOKEN"]
BASE_URL = os.environ["RENDER_EXTERNAL_URL"]  # Например: https://my-bot.onrender.com
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

# -------------------------------------------------
# Flask
# -------------------------------------------------
flask_app = Flask(__name__)

# -------------------------------------------------
# Telegram Application (async)
# -------------------------------------------------
application = Application.builder().token(BOT_TOKEN).build()
loop = asyncio.get_event_loop()

# -------------------------------------------------
# Google Sheets setup
# -------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds_json = os.environ.get("GOOGLE_CREDS_JSON")  # JSON строки из Render env
if creds_json:
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    try:
        SHEET = gc.open("бот фукуок вьетнам").sheet1  # Новое название таблицы
        logger.info("Google Sheets подключена")
    except Exception as e:
        SHEET = None
        logger.error(f"Не удалось открыть таблицу: {e}")
else:
    SHEET = None
    logger.warning("Google Sheets credentials не найдены. Ответы не сохраняются.")

# -------------------------------------------------
# Handlers
# -------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✅ Был", callback_data="been"),
            InlineKeyboardButton("❌ Не был", callback_data="not_been"),
        ],
        [
            InlineKeyboardButton("⭐ Хочу побывать", callback_data="want"),
            InlineKeyboardButton("⏭ Пропустить", callback_data="skip"),
        ],
    ]

    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Я буду задавать вопросы о местах на острове Фукуок 🇻🇳\n"
        "Отвечай кнопками ниже 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    username_or_id = user.username or str(user.id)

    answer_map = {
        "been": "Был",
        "not_been": "Не был",
        "want": "Хочу побывать",
        "skip": "Пропущено",
    }

    answer = answer_map.get(query.data, "Неизвестно")

    # Сохраняем в Google Sheets (если подключено)
    if SHEET:
        try:
            SHEET.append_row([username_or_id, answer])
        except Exception as e:
            logger.error(f"Ошибка при записи в Google Sheets: {e}")

    await query.edit_message_text(
        text=f"Спасибо за ответ 🙌\n\n"
             f"👤 Пользователь: {username_or_id}\n"
             f"📌 Ответ: {answer}"
    )


# -------------------------------------------------
# Register handlers
# -------------------------------------------------
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(buttons))

# -------------------------------------------------
# Webhook Flask routes
# -------------------------------------------------
@flask_app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    loop.run_until_complete(application.process_update(update))
    return "OK", 200

# -------------------------------------------------
# Setup webhook
# -------------------------------------------------
async def setup_webhook():
    await application.initialize()  # <- важно для PTB v22+
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

loop.run_until_complete(setup_webhook())

# -------------------------------------------------
# Entrypoint for Gunicorn / Render
# -------------------------------------------------
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=10000)
