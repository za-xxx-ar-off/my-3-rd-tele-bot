import os
import threading
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import db
import sheets


# ================= ENV =================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
PORT = int(os.environ.get("PORT", 5000))


# ================= KEYBOARDS =================

def keyboard_start():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Да", callback_data="start_yes"),
            InlineKeyboardButton("Нет", callback_data="start_no"),
        ]
    ])


def keyboard_answers():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Был ✅", callback_data="yes")],
        [InlineKeyboardButton("Не был ❌", callback_data="no")],
        [InlineKeyboardButton("Хотел бы побывать ⭐", callback_data="want")],
    ])


# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Готовы ли вы пройти тестирование?",
        reply_markup=keyboard_start()
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # игнорируем обычный текст
    pass


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
            chat_id=chat_id,
            photo=image,
            caption=question,
            reply_markup=keyboard_answers()
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=question,
            reply_markup=keyboard_answers()
        )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat = query.message.chat
    chat_id = chat.id

    # старт
    if query.data == "start_yes":
        db.set(chat_id, 2)  # начинаем со 2 строки (1 — заголовки)
        await send_question(chat_id, context)
        return

    if query.data == "start_no":
        await context.bot.send_message(
            chat_id,
            "Хорошо, если понадоблюсь — обращайтесь по команде /start"
        )
        return

    # ответы
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


# ================= APP =================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
app.add_handler(CallbackQueryHandler(callback))


# ================= FLASK (для Render) =================

flask_app = Flask(__name__)


@flask_app.route("/")
def health():
    return "OK", 200


# ================= ENTRY =================

if __name__ == "__main__":
    db.init()
    threading.Thread(target=app.run_polling, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=PORT)
