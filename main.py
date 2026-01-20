import os
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import gspread
from google.oauth2.service_account import Credentials

# ===== ENV =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
PORT = int(os.environ.get("PORT", 10000))
GSHEET_CRED_JSON = os.environ["GSHEET_CRED_JSON"]  # JSON credentials в виде строки
GSHEET_NAME = os.environ.get("GSHEET_NAME", "Sheet1")

# ===== GOOGLE SHEETS =====
creds_dict = eval(GSHEET_CRED_JSON)  # Конвертируем строку в dict
creds = Credentials.from_service_account_info(creds_dict)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(creds_dict["private_key_id"]).sheet1  # или по имени

# ===== BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает через webhook ✅")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /add <текст>")
        return
    text = " ".join(context.args)
    sheet.append_row([text])
    await update.message.reply_text(f"Добавлено: {text}")

async def list_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values = sheet.get_all_values()
    if not values:
        await update.message.reply_text("Таблица пуста.")
    else:
        text = "\n".join([", ".join(row) for row in values])
        await update.message.reply_text(f"Содержимое таблицы:\n{text}")

# ===== APPLICATION =====
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add))
application.add_handler(CommandHandler("list", list_sheet))

# Инициализация бота один раз
asyncio.run(application.initialize())
asyncio.run(application.start())

# ===== FLASK =====
flask_app = Flask(__name__)

@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)
