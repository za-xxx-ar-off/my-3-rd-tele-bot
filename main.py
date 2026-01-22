import os
import sys
import json
import re
import logging
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import Conflict, TelegramError

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

FIRST_QUESTION_ROW = 2
QUESTION_COL = 2  # B
IMAGE_COL = 1     # A

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


def _find_next_question_row(sheet, start_row: int) -> int | None:
    """Ищет следующую строку с непустым вопросом в колонке QUESTION_COL."""
    try:
        all_values = sheet.get_all_values()
        max_row = len(all_values) if all_values else 0
        row = start_row
        while row <= max_row:
            val = sheet.cell(row, QUESTION_COL).value
            if val and val.strip():
                return row
            row += 1
        return None
    except Exception:
        logger.exception("❌ Ошибка при поиске следующего вопроса")
        return None


async def _send_question_by_row(update_or_query, context: ContextTypes.DEFAULT_TYPE, row: int):
    """Отправляет вопрос (картинка + текст или только текст) в чат."""
    if SHEET is None:
        if hasattr(update_or_query, "reply_text"):
            await update_or_query.reply_text("Ошибка: Google Sheets недоступна.")
        else:
            await update_or_query.message.reply_text("Ошибка: Google Sheets недоступна.")
        return

    image_url = drive_to_direct(SHEET.cell(row, IMAGE_COL).value)
    question_text = SHEET.cell(row, QUESTION_COL).value or " "

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
        if hasattr(update_or_query, "reply_photo"):
            await update_or_query.reply_photo(photo=image_url, caption=question_text)
        else:
            await update_or_query.message.reply_photo(photo=image_url, caption=question_text)
    else:
        if hasattr(update_or_query, "reply_text"):
            await update_or_query.reply_text(question_text)
        else:
            await update_or_query.message.reply_text(question_text)

    if hasattr(update_or_query, "reply_text"):
        await update_or_query.reply_text("Выбери вариант 👇", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.message.reply_text("Выбери вариант 👇", reply_markup=InlineKeyboardMarkup(keyboard))


# -------------------------------------------------
# HANDLERS
# -------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инициализация: находим первый вопрос и отправляем его."""
    if SHEET is None:
        await update.message.reply_text("Ошибка: Google Sheets не подключена.")
        return

    row = _find_next_question_row(SHEET, FIRST_QUESTION_ROW)
    if row is None:
        await update.message.reply_text("Вопросы не найдены. Обратитесь к администратору.")
        return

    context.user_data["row"] = row
    await _send_question_by_row(update.message, context, row)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок — запись ответа, защита от перезаписи, автопереход."""
    query = update.callback_query
    await query.answer()

    if SHEET is None:
        await query.edit_message_text("Ошибка: Google Sheets не подключена.")
        return

    row = context.user_data.get("row")
    if not row:
        await query.edit_message_text("Прогресс не найден. Нажмите /start, чтобы начать.")
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
    except Exception:
        logger.exception("❌ Ошибка получения колонки пользователя")
        await query.edit_message_text("Ошибка при определении колонки для записи.")
        return

    try:
        existing = SHEET.cell(row, col).value
        if existing and existing.strip():
            await query.edit_message_text(f"Вы уже ответили на этот вопрос ранее.\n\n👤 {username}\n📌 {existing}")
            next_row = _find_next_question_row(SHEET, row + 1)
            if next_row is None:
                keyboard = ReplyKeyboardMarkup([["/start"]], one_time_keyboard=True, resize_keyboard=True)
                await query.message.reply_text("Вопросы закончились. Нажмите /start, чтобы начать заново.", reply_markup=keyboard)
                context.user_data.pop("row", None)
                return
            context.user_data["row"] = next_row
            await _send_question_by_row(query, context, next_row)
            return

        SHEET.update_cell(row, col, answer)
    except Exception:
        logger.exception("❌ Ошибка записи в Google Sheets")
        await query.edit_message_text("Ошибка при записи ответа. Попробуйте позже.")
        return

    await query.edit_message_text(f"Спасибо 🙌\n\n👤 {username}\n📌 {answer}")

    next_row = _find_next_question_row(SHEET, row + 1)
    if next_row is None:
        keyboard = ReplyKeyboardMarkup([["/start"]], one_time_keyboard=True, resize_keyboard=True)
        await query.message.reply_text("Вопросы закончились. Нажмите /start, чтобы начать заново.", reply_markup=keyboard)
        context.user_data.pop("row", None)
        return

    context.user_data["row"] = next_row
    await _send_question_by_row(query, context, next_row)


# -------------------------------------------------
# MAIN (polling only)
# -------------------------------------------------
def _build_application():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    return app

def main():
    application = _build_application()
    logger.info("🤖 Подготовка к запуску бота (polling)")

    async def _run_polling():
        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("🧹 Старый webhook удалён, pending updates сброшены")
        except TelegramError:
            logger.exception("⚠️ Не удалось удалить webhook (игнорируем)")

        logger.info("🚀 Запуск polling (drop_pending_updates=True)")
        await application.run_polling(drop_pending_updates=True)

    try:
        asyncio.run(_run_polling())
    except Conflict:
        logger.exception("❌ Conflict: другой getUpdates уже запущен. Убедитесь, что запущен только один экземпляр бота.")
        sys.exit(2)
    except Exception:
        logger.exception("❌ Неожиданная ошибка при запуске бота")
        sys.exit(1)


if __name__ == "__main__":
    # Инициализация Google Sheets
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

    main()
