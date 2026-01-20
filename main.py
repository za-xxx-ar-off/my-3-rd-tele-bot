import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# -----------------------------
# Настройки из переменных окружения
# -----------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
PORT = int(os.environ.get("PORT", 5000))

# -----------------------------
# Здесь подключаем вашу "db" и "sheets"
# Например, db.py и sheets.py в корне проекта
# -----------------------------
import db          # ваш модуль для хранения прогресса
import sheets      # ваш модуль для тестов и Google Sheets

# -----------------------------
# Заготовка для клавиатуры и хендлеров
# -----------------------------
def keyboard_answers():
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [InlineKeyboardButton("Был", callback_data="yes"),
         InlineKeyboardButton("Не был", callback_data="no"),
         InlineKeyboardButton("Хотел бы побывать", callback_data="maybe")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.set(chat_id, 1)  # старт с первой строки
    await send_question(chat_id, context)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # здесь можно обрабатывать текстовые сообщения
    await update.message.reply_text("Используйте кнопки для ответа")

# -----------------------------
# Функция отправки вопроса
# -----------------------------
async def send_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    row = db.get(chat_id)
    if not row:
        return

    if row > sheets.total_rows():
        await context.bot.send_message(chat_id, "Тест завершён, спасибо!")
        db.clear(chat_id)
        return

    image, question = sheets.get_test(row)

    if image:
        await context.bot.send_photo(
            chat_id,
            image,
            caption=question,
            reply_markup=keyboard_answers()
        )
    else:
        await context.bot.send_message(
            chat_id,
            question,
            reply_markup=keyboard_answers()
        )

# -----------------------------
# Обработка кнопок
# -----------------------------
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat = query.message.chat
    chat_id = chat.id

    row = db.get(chat_id)
    if not row:
        return

    if query.data == "yes":
        answer = "Был"
    elif query.data == "no":
        answer = "Не был"
    else:
        answer = "Хотел бы побывать"

    user = f"@{chat.username}" if chat.username else f"id_{chat_id}"

    col = sheets.get_or_create_user_column(user)
    sheets.save_answer(row, col, answer)

    db.set(chat_id, row + 1)
    await send_question(chat_id, context)

# -----------------------------
# Telegram бот
# -----------------------------
bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
bot_app.add_handler(CallbackQueryHandler(callback))

# -----------------------------
# Flask для Render / health check
# -----------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "OK", 200

# -----------------------------
# Запуск
# -----------------------------
if __name__ == "__main__":
    db.init()
    # Запускаем Telegram бота в отдельном потоке
    threading.Thread(target=bot_app.run_polling, daemon=True).start()
    # Запуск Flask через Gunicorn
    flask_app.run(host="0.0.0.0", port=PORT)
