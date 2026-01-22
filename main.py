import os
import json
import logging
import re

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
IMAGE_URL = None
QUESTION_TEXT = None


def drive_to_direct(url: str | None) -> str | None:
    """Преобразует ссылку Google Drive в прямую ссылку"""
    if not url:
        return None

    if "drive.google.com" not in url:
        return url

    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return None

    file_id = match.group(1)
    return f"https://drive.google.com/uc?id={file_id}"


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

    # читаем данные
    IMAGE_URL = drive_to_direct(SHEET.acell("A1").value)
    QUESTION_TEXT = SHEET.acell("A2").value

    logger.info(f"📄 Найдена таблица: {sh.title}")
    logger.info(f"🖼 IMAGE_URL: {IMAGE_URL}")
    logger.info(f"📝 QUESTION_TEXT: {QUESTION_TEXT}")
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

    # отправляем фото + текст
    if IMAGE_URL:
        await update.message.reply_photo(
            photo=IMAGE_URL,
            caption=QUESTION_TEXT or " "
        )
    else:
        await update.message.reply_text(
            QUESTION_TEXT or " "
        )

    await update.message.reply_text(
        "Выбери вариант 👇",
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
