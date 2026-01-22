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


def drive_to_direct(url: str | None) -> str | None:
    """Google Drive → прямая ссылка"""
    if not url:
        return None

    if "drive.google.com" not in url:
        return url

    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return None

    return f"https://drive.google.com/uc?id={match.group(1)}"


def get_user_column(sheet, username: str) -> int:
    """Возвращает колонку пользователя, создаёт если нет"""
    header = sheet.row_values(1)

    if username in header:
        return header.index(username) + 1

    col = len(header) + 1
    sheet.update_cell(1, col, username)
    return col


try:
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
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
    row = 2  # текущий вопрос
    context.user_data["row"] = row

    image_url = drive_to_direct(SHEET.cell(row, 1).value)
    question_text = SHEET.cell(row, 2).value

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

    if image_url:
        await update.message.reply_photo(
            photo=image_url,
            caption=question_text or " "
        )
    else:
        await update.message.reply_text(question_text or " ")

    await update.message.reply_text(
        "Выбери вариант 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    row = context.user_data.get("row")
    if not row:
        return

    user = query.from_user
    username = f"@{user.username}" if user.username else str(user.id)

    answer_map = {
        "been": "Был",
        "not_been": "Не был",
        "want": "Хочу побывать",
        "skip": "Пропущено",
    }

    answer = answer_map.get(query.data, "—")

    try:
        col = get_user_column(SHEET, username)
        SHEET.update_cell(row, col, answer)
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
