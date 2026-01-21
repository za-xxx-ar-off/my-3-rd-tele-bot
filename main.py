import os
import asyncio
import logging

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

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
BASE_URL = os.environ["RENDER_EXTERNAL_URL"]
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

# -------------------------------------------------
# Flask
# -------------------------------------------------
flask_app = Flask(__name__)

# -------------------------------------------------
# Telegram Application
# -------------------------------------------------
application = Application.builder().token(BOT_TOKEN).build()
loop = asyncio.get_event_loop()

# -------------------------------------------------
# Google Sheets
# -------------------------------------------------
SHEET = None
try:
    client_email = os.environ.get("GOOGLE_CLIENT_EMAIL")
    private_key = os.environ.get("GOOGLE_PRIVATE_KEY")

    if client_email and private_key:
        creds = Credentials.from_service_account_info(
            {
                "type": "service_account",
                "client_email": client_email,
                "private_key": private_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            },
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )

        gc = gspread.authorize(creds)
        SHEET = gc.open("бот фукуок вьетнам").sheet1
        logger.info("✅ Google Sheets подключена")

    else:
        logger.warning("Google Sheets credentials не заданы")

except Exception as e:
    logger.error(f"❌ Google Sheets ошибка: {e}")
    SHEET = None

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
        SHEET.append_row([username, answer])

    await query.edit_message_text(
        f"Спасибо 🙌\n\n👤 {username}\n📌 {answer}"
    )

# -------------------------------------------------
# Register handlers
# -------------------------------------------------
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(buttons))

# -------------------------------------------------
# Webhook routes
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
# Webhook setup
# -------------------------------------------------
async def setup():
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

loop.run_until_complete(setup())
