import os
import json
import logging

from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
)

import gspread
from google.oauth2.service_account import Credentials


# ================== CONFIG ==================

BOT_TOKEN = os.environ["BOT_TOKEN"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
GSHEET_CRED_JSON = os.environ["GSHEET_CRED_JSON"]

WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO)

# ================== GOOGLE SHEETS ==================

def get_sheet():
    creds_dict = json.loads(GSHEET_CRED_JSON)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_info(
        creds_dict, scopes=scopes
    )

    gc = gspread.authorize(credentials)
    return gc.open_by_key(SPREADSHEET_ID).sheet1


def get_user_key(user):
    if user.username:
        return f"@{user.username}"
    return f"id_{user.id}"


def find_next_row(sheet, user_key):
    headers = sheet.row_values(1)

    user_col = None
    if user_key in headers:
        user_col = headers.index(user_key) + 1

    for row in range(2, sheet.row_count + 1):
        if user_col is None:
            return row

        value = sheet.cell(row, user_col).value
        if not value:
            return row

    return None


def save_answer(sheet, row, user_key, answer):
    headers = sheet.row_values(1)

    if user_key not in headers:
        col = len(headers) + 1
        sheet.update_cell(1, col, user_key)
    else:
        col = headers.index(user_key) + 1

    sheet.update_cell(row, col, answer)


# ================== BOT LOGIC ==================

async def start(update: Update, context):
    sheet = get_sheet()
    user_key = get_user_key(update.effective_user)

    row = find_next_row(sheet, user_key)

    if not row:
        await update.message.reply_text(
            "Ты уже ответил на все вопросы 🙌"
        )
        return

    await send_place(update, context, row)


async def send_place(update: Update, context, row: int):
    sheet = get_sheet()

    photo = sheet.cell(row, 1).value
    text = sheet.cell(row, 2).value

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Был", callback_data=f"ans|{row}|been"),
            InlineKeyboardButton("❌ Не был", callback_data=f"ans|{row}|not"),
        ],
        [
            InlineKeyboardButton("⭐ Хочу побывать", callback_data=f"ans|{row}|want"),
            InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip|{row}"),
        ]
    ])

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=photo,
        caption=text,
        reply_markup=keyboard
    )


async def handle_answer(update: Update, context):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    action = data[0]
    row = int(data[1])

    sheet = get_sheet()
    user_key = get_user_key(query.from_user)

    if action == "ans":
        answer = data[2]
        save_answer(sheet, row, user_key, answer)

    next_row = find_next_row(sheet, user_key)

    if next_row:
        await send_place(update, context, next_row)
    else:
        await query.message.reply_text(
            "Спасибо! Все места пройдены 🙌"
        )


# ================== FLASK + WEBHOOK ==================

flask_app = Flask(__name__)

application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_answer))


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    update = Update.de_json(
        request.get_json(force=True),
        application.bot
    )
    await application.process_update(update)
    return "OK"


@flask_app.route("/", methods=["GET"])
def health():
    return "Bot is running"


async def setup_webhook():
    await application.bot.set_webhook(WEBHOOK_URL)


import asyncio
asyncio.get_event_loop().run_until_complete(setup_webhook())
