import os
import json
import logging

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
# LOGGING
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# ENV
# -------------------------------------------------
BOT_TOKEN = os.environ["BOT_TOKEN"]

# -------------------------------------------------
# GOOGLE SHEETS
# -------------------------------------------------
SHEET = None

try:
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDS_JSON не задан")

    creds_dict = json.loads(creds_json)
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    gc = gspread.authorize(creds)
    sh = gc.open("бот фукуок вьетнам")
    SHEET = sh.sheet1

    logger.info(f"📄 Найдена таблица: {sh.title}")
    logger.info("✅ Google Sheets подключена")

except Exception:
    logger.exception("❌ Google Sheets ошибка")
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
        except Exception:
            logger.exception("❌ Ошибка записи в Google Sheets")

    await query.edit_message_text(
        f"Спасибо 🙌\n\n👤 {username}\n📌 {answer}"
    )

# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(buttons))

    logger.info("🤖 Бот запущен (polling)")
    application.run_polling()


if __name__ == "__main__":
    main()
