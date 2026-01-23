import os
import sys
import json
import re
import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from telegram.error import Conflict

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
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")  # Опционально для безопасности

# -------------------------------------------------
# GOOGLE SHEETS CONFIG
# -------------------------------------------------
SHEET = None

FIRST_QUESTION_ROW = 2

PHOTO_COL = 1      # A
TEXT_COL = 2       # B
USERS_START_COL = 4  # D

# -------------------------------------------------
# KEYBOARDS
# -------------------------------------------------
RESTART_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🔄 Начать заново", callback_data="restart")]]
)

ANSWER_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("✅ Был", callback_data="been"),
            InlineKeyboardButton("❌ Не был", callback_data="not_been"),
        ],
        [
            InlineKeyboardButton("⭐ Хочу побывать", callback_data="want"),
            InlineKeyboardButton("⏭ Пропустить", callback_data="skip"),
        ],
    ]
)

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def drive_to_direct(url: str | None) -> str | None:
    if not url:
        return None

    url = url.strip()

    if not url.startswith("http"):
        return None

    if "drive.google.com" not in url:
        return url

    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return None

    return f"https://drive.google.com/uc?id={match.group(1)}"


def get_user_column(sheet, username: str) -> int:
    header = sheet.row_values(1)

    for idx in range(USERS_START_COL - 1, len(header)):
        if header[idx] == username:
            return idx + 1

    col = max(len(header) + 1, USERS_START_COL)
    sheet.update_cell(1, col, username)
    return col


def find_next_question_row(sheet, start_row: int) -> int | None:
    values = sheet.get_all_values()

    for row in range(start_row, len(values) + 1):
        if sheet.cell(row, TEXT_COL).value:
            return row

    return None


async def send_question(bot_app: Application, target, row: int):
    raw_image = SHEET.cell(row, PHOTO_COL).value
    image = drive_to_direct(raw_image)
    text = SHEET.cell(row, TEXT_COL).value or ""

    if image:
        await target.reply_photo(photo=image, caption=text)
    else:
        await target.reply_text(text)

    await target.reply_text("Выбери вариант 👇", reply_markup=ANSWER_KEYBOARD)

# -------------------------------------------------
# HANDLERS
# -------------------------------------------------
async def start(update: Update, context):
    row = find_next_question_row(SHEET, FIRST_QUESTION_ROW)

    if row is None:
        await update.message.reply_text("Вопросы не найдены.")
        return

    context.user_data["row"] = row
    await send_question(context.application, update.message, row)


async def buttons(update: Update, context):
    query = update.callback_query
    await query.answer()

    # restart
    if query.data == "restart":
        context.user_data.clear()
        row = find_next_question_row(SHEET, FIRST_QUESTION_ROW)

        if row is None:
            await query.edit_message_text("Вопросы не найдены.")
            return

        context.user_data["row"] = row
        await send_question(context.application, query.message, row)
        return

    row = context.user_data.get("row")
    if not row:
        await query.edit_message_text("Нажмите /start")
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

    # 🔥 ВАЖНО: ВСЕГДА ОБНОВЛЯЕМ ОТВЕТ
    col = get_user_column(SHEET, username)
    SHEET.update_cell(row, col, answer)

    await query.edit_message_text(
        f"Ответ сохранён 🙌\n\n👤 {username}\n📌 {answer}"
    )

    next_row = find_next_question_row(SHEET, row + 1)

    if next_row is None:
        await query.message.reply_text(
            "✅ Вопросы закончились.\n\nХочешь пройти опрос ещё раз?",
            reply_markup=RESTART_KEYBOARD
        )
        context.user_data.clear()
        return

    context.user_data["row"] = next_row
    await send_question(context.application, query.message, next_row)

# -------------------------------------------------
# FASTAPI APP
# -------------------------------------------------
app = FastAPI()

# Инициализация бота и диспетчера
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(buttons))

@app.get("/ping")
async():
    """Endpoint для мониторинга, чтобы Render не засыпал"""
    return PlainTextResponse("OK")

@app.post("/webhook")
async(request: Request, background_tasks: BackgroundTasks):
    """Webhook endpoint для Telegram"""
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return PlainTextResponse("Unauthorized", status_code=401)

    json_data = await request.json()
    update = Update.de_json(json_data, application.bot)

    if update:
        background_tasks.add_task(application.process_update, update)

    return PlainTextResponse("OK")

@app.on_event("startup")
async def on_startup():
    """Установка webhook при запуске"""
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'your-app.onrender.com')}/webhook"
    await application.bot.set_webhook(webhook_url)
    logger.info(f"Webhook установлен: {webhook_url}")

@app.on_event("shutdown")
async def on_shutdown():
    """Удаление webhook при остановке"""
    await application.bot.delete_webhook()
    logger.info("Webhook удалён")

# -------------------------------------------------
# GOOGLE SHEETS INIT
# -------------------------------------------------
try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    gc = gspread.authorize(creds)
    SHEET = gc.open("бот фукуок вьетнам").sheet1

    logger.info("✅ Google Sheets подключена")

except Exception as e:
    logger.exception("❌ Ошибка Google Sheets")
    SHEET = None

# -------------------------------------------------
# MAIN
# -------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(
        "main:app",  # Замените 'main' на имя вашего файла без .py
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
