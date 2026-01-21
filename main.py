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
# ЛОГИ
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# ENV
# -------------------------------------------------
BOT_TOKEN = os.environ["BOT_TOKEN"]
BASE_URL = os.environ["RENDER_EXTERNAL_URL"]

WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

# -------------------------------------------------
# FLASK
# -------------------------------------------------
flask_app = Flask(__name__)

# -------------------------------------------------
# TELEGRAM APPLICATION
# -------------------------------------------------
application = Application.builder().token(BOT_TOKEN).build()
loop = asyncio.get_event_loop()

# -------------------------------------------------
# GOOGLE SHEETS
# -------------------------------------------------
SHEET = None

try:
    # В Render удобно хранить весь JSON в одной переменной
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDS_JSON не задан")

    creds_dict = json.loads(creds_json)

    # Восстанавливаем переносы строк в private_key
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )

    gc = gspread.authorize(creds)
    SHEET = gc.open("бот фукуок вьетнам").sheet1

    logger.info("✅ Google Sheets подключена")

except Exception as e:
    logger.error(f"❌ Google Sheets ошибка: {e}")
    SHEET = None

# -------------------------------------------------
# HANDLERS
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
        "Я буду задавать вопросы о местах на острове Фукуок 🇻🇳",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    username = user.username or str(user.id)

    answer_map = {
        "been": "Был",
        "not_been": "Не был",
        "want": "Хочу побывать",
        "skip": "Пропущено",
    }

    answer = answer_map.get(query.data, "Неизвестно")

    if SHEET:
        try:
            SHEET.append_row([username, answer])
        except Exception as e:
            logger.error(f"Ошибка записи в Google Sheets: {e}")

    await query.edit_message_text(
        f"Спасибо 🙌\n\n👤 {username}\n📌 {answer}"
    )

# -------------------------------------------------
# REGISTER HANDLERS
# -------------------------------------------------
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(buttons))

# -------------------------------------------------
# FLASK ROUTES
# -------------------------------------------------
@flask_app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    loop.run_until_complete(application.process_update(update))
    return "OK", 200

# -------------------------------------------------
# WEBHOOK SETUP
# -------------------------------------------------
async def setup():
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

loop.run_until_complete(setup())
