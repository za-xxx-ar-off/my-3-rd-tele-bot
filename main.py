import os
import json
import asyncio
import logging

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# -------------------------------------------------
# ЛОГИ
# -------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# ENV
# -------------------------------------------------
BOT_TOKEN = os.environ["BOT_TOKEN"]  # токен бота
BASE_URL = os.environ["RENDER_EXTERNAL_URL"]  # https://xxx.onrender.com

WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

# -------------------------------------------------
# FLASK
# -------------------------------------------------
flask_app = Flask(__name__)

# -------------------------------------------------
# TELEGRAM APPLICATION (ASYNC)
# -------------------------------------------------
application = Application.builder().token(BOT_TOKEN).build()

# создаём event loop ОДИН раз
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# -------------------------------------------------
# JSON ФАЙЛ ДЛЯ ОТВЕТОВ
# -------------------------------------------------
JSON_FILE = "answers.json"

# Создаём файл если не существует
if not os.path.exists(JSON_FILE):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=4)

def save_answer(user_id, username, answer):
    """Сохраняет ответ пользователя в JSON файл"""
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    data[str(user_id)] = {
        "username": username,
        "answer": answer
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
        "Я буду задавать вопросы о местах на острове Фукуок 🇻🇳\n"
        "Отвечай кнопками ниже 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    username_or_id = user.username or str(user.id)

    answer_map = {
        "been": "Был",
        "not_been": "Не был",
        "want": "Хочу побывать",
        "skip": "Пропущено",
    }

    answer = answer_map.get(query.data, "Неизвестно")

    # Сохраняем ответ в JSON
    save_answer(user.id, username_or_id, answer)

    await query.edit_message_text(
        text=f"Спасибо за ответ 🙌\n\n"
             f"👤 Пользователь: {username_or_id}\n"
             f"📌 Ответ: {answer}"
    )

# -------------------------------------------------
# REGISTER HANDLERS
# -------------------------------------------------
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(buttons))

# -------------------------------------------------
# FLASK ROUTES
# -------------------------------------------------
@flask_app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)

    # Обработка update синхронно через loop
    loop.run_until_complete(application.process_update(update))
    return "OK", 200

# -------------------------------------------------
# WEBHOOK SETUP
# -------------------------------------------------
async def setup_webhook():
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

loop.run_until_complete(setup_webhook())

# -------------------------------------------------
# ENTRYPOINT FOR GUNICORN
# -------------------------------------------------
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=10000)
