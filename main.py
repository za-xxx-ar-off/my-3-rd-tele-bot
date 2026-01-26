import os
import json
import re
import logging
import time
from functools import lru_cache

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

# -------------------------------------------------
# GOOGLE SHEETS + КЭШ
# -------------------------------------------------
SHEET = None
user_cache = {}  # username → column
cache_time = {}  # username → timestamp

FIRST_QUESTION_ROW = 2
PHOTO_COL = 1      # A
TEXT_COL = 2       # B
USERS_START_COL = 4  # D

# -------------------------------------------------
# KEYBOARDS
# -------------------------------------------------
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

RESTART_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🔄 Начать заново", callback_data="restart")]]
)

# -------------------------------------------------
# HELPERS (с КЭШЕМ)
# -------------------------------------------------
def drive_to_direct(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if "drive.google.com" not in url:
        return url

    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        return None

    return f"https://drive.google.com/uc?id={m.group(1)}"

def get_user_column_cached(username: str) -> int | None:
    """🔥 КЭШ НА 10 МИНУТ - ИСПРАВЛЯЕТ 429 ERROR"""
    now = time.time()
    
    # Проверяем кэш
    if username in user_cache and now - cache_time.get(username, 0) < 600:
        return user_cache[username]
    
    try:
        # Оригинальная функция
        header = SHEET.row_values(1)
        for i in range(USERS_START_COL - 1, len(header)):
            if header[i] == username:
                user_cache[username] = i + 1
                cache_time[username] = now
                return i + 1

        col = max(len(header) + 1, USERS_START_COL)
        SHEET.update_cell(1, col, username)
        user_cache[username] = col
        cache_time[username] = now
        return col
        
    except Exception as e:
        logger.error(f"Cache error: {e}")
        return user_cache.get(username)  # Возвращаем старый кэш

def find_next_question_row(sheet, start: int) -> int | None:
    values = sheet.get_all_values()
    for row in range(start, len(values) + 1):
        if sheet.cell(row, TEXT_COL).value:
            return row
    return None

async def send_question(message, row: int):
    try:
        image_cell = SHEET.cell(row, PHOTO_COL).value
        text = SHEET.cell(row, TEXT_COL).value or ""
        
        # 🔥 ПРОВЕРКА КАРТИНКИ
        image = drive_to_direct(image_cell)
        if image and "drive.google.com" in image_cell:
            # ТЕСТ: отправляем ТОЛЬКО текст при проблемах с Drive
            await message.reply_text(f"📍 {text}\n\n[Картинка временно недоступна]", 
                                   reply_markup=ANSWER_KEYBOARD)
            return
            
        if image:
            await message.reply_photo(photo=image, caption=text)
        else:
            await message.reply_text(f"📍 {text}", reply_markup=ANSWER_KEYBOARD)
            
    except Exception as e:
        logger.error(f"Send question error: {e}")
        await message.reply_text("❌ Временная ошибка. Попробуйте /start", 
                               reply_markup=ANSWER_KEYBOARD)

# -------------------------------------------------
# ERROR HANDLER
# -------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔥 СКРЫВАЕТ ОШИБКИ ОТ ПОЛЬЗОВАТЕЛЕЙ"""
    logger.error(f"Bot error: {context.error}")

# -------------------------------------------------
# HANDLERS
# -------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        row = find_next_question_row(SHEET, FIRST_QUESTION_ROW)
        if row is None:
            await update.message.reply_text("Вопросы не найдены.")
            return

        context.user_data.clear()
        context.user_data["row"] = row
        await send_question(update.message, row)
    except Exception:
        await update.message.reply_text("Попробуйте позже /start")

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
            await send_question(query.message, row)
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

        col = get_user_column_cached(username)  # 🔥 КЭШ!
        if col:
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
        await send_question(query.message, next_row)
        
    except Exception:
        await update.callback_query.edit_message_text("Ошибка. Нажмите /start")

# -------------------------------------------------
# FASTAPI + TELEGRAM
# -------------------------------------------------
app = FastAPI()

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(buttons))
telegram_app.add_error_handler(error_handler)  # 🔥 ERROR HANDLER

@app.on_event("startup")
async def on_startup():
    global SHEET
    await telegram_app.initialize()
    webhook_url = f"https://{RENDER_HOST}/webhook"
    await telegram_app.bot.set_webhook(webhook_url)
    logger.info(f"🚀 Webhook установлен: {webhook_url}")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return PlainTextResponse("OK")

@app.get("/ping")
async def ping():
    return PlainTextResponse("OK")

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

except Exception:
    logger.exception("❌ Ошибка Google Sheets")
