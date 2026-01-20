import os
import json
from flask import Flask, request

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import gspread
from google.oauth2.service_account import Credentials

# ========= ENV =========
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GSHEET_CRED_JSON = os.environ["GSHEET_CRED_JSON"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]  # ID таблицы из URL

# ========= GOOGLE SHEETS =========
creds_dict = json.loads(GSHEET_CRED_JSON)
scopes = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# ========= BOT HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает через webhook ✅")

async def add_row(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет строку в Google Sheet"""
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Надо указать текст после команды, например:\n/addrow Привет мир")
        return
    sheet.append_row([text])
    await update.message.reply_text(f"Добавлено в таблицу: {text}")

async def get_row(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает последнюю строку таблицы"""
    rows = sheet.get_all_values()
    if rows:
        await update.message.reply_text(f"Последняя строка: {rows[-1]}")
    else:
        await update.message.reply_text("Таблица пуста.")

# ========= TELEGRAM =========
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("addrow", add_row))
application.add_handler(CommandHandler("getrow", get_row))

# ========= FLASK =========
flask_app = Flask(__name__)

@flask_app.post(f"/{TELEGRAM_TOKEN}")
def telegram_webhook():
    from telegram import Update
    update = Update.de_json(request.get_json(force=True), application.bot)
    import asyncio
    asyncio.run(application.process_update(update))  # безопасно в Flask
    return "OK", 200

@flask_app.get("/")
def health():
    return "OK", 200
