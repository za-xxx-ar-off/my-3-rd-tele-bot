import os
import json
import asyncio
import logging

from flask import Flask, request
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
# ЛОГИ
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
# FLASK
# -------------------------------------------------
flask_app = Flask(__name__)

# -------------------------------------------------
# TELEGRAM APPLICATION
# -------------------------------------------------
application = Application.builder().token(BOT_TOKEN).build()
loop = asyncio.get_event_loop()

# -------------------------------------------------
# GOOGLE SHEETS
# -------------------------------------------------
SHEET = None

try:
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")

    if not creds_json:
        raise RuntimeError("GOOGLE_CREDS_JSON не задан")

    creds_dict = json.loads(creds_json)

    # 🔥 КЛЮЧЕВОЙ МОМЕНТ — ВОССТАНОВЛЕНИЕ ПЕРЕНОСОВ СТРОК
    creds_dict["priv]()_
