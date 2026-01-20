import os
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

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


app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
app.add_handler(CallbackQueryHandler(callback))


flask_app = Flask(__name__)


@flask_app.route("/")
def health():
    return "OK", 200


if __name__ == "__main__":
    db.init()
    threading.Thread(target=app.run_polling, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=PORT)
