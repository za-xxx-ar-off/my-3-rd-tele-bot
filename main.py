import os
import json
import logging
import asyncio
import gspread
from aiohttp import web

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
SHEET_ID = os.environ["SHEET_ID"]
SERVICE_ACCOUNT_JSON = os.environ["SERVICE_ACCOUNT_JSON"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", 10000))

# ===== GOOGLE SHEETS =====
creds = json.loads(SERVICE_ACCOUNT_JSON)
gc = gspread.service_account_from_dict(creds)
sh = gc.open_by_key(SHEET_ID)
ws = sh.sheet1

# ===== CACHE =====
CACHE = {}

# ===== GOOGLE DRIVE =====
def convert_drive_url(url: str) -> str:
    if "drive.google.com" in url:
        try:
            if "/file/d/" in url:
                file_id = url.split("/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            else:
                return url
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        except:
            return url
    return url

# ===== TEXTS =====
TEXTS = {
    "ru": {
        "menu": "Чем я могу помочь?",
        "catalog": "Каталог",
        "contact": "Связаться",
        "location": "Местоположение",
        "more": "Еще",
        "back": "Назад",
        "next": "Еще или Назад?",
        "finished": "Фото закончились, выбрать другую категорию?",
        "yes": "Да",
        "no": "Нет",

        "kitchen": "Кухонные гарнитуры",
        "bedroom": "Спальни",
        "other": "Остальная мебель",
        "soft": "Мягкая мебель",
        "video": "Видео"
    },
    "uz": {
        "menu": "Qanday yordam bera olaman?",
        "catalog": "Katalog",
        "contact": "Bog‘lanish",
        "location": "Joylashuv",
        "more": "Yana",
        "back": "Orqaga",
        "next": "Yana yoki Orqaga?",
        "finished": "Rasmlar tugadi, boshqa bo‘lim tanlaysizmi?",
        "yes": "Ha",
        "no": "Yo‘q",

        "kitchen": "Oshxona garniturlari",
        "bedroom": "Yotoqxonalar",
        "other": "Boshqa mebellar",
        "soft": "Yumshoq mebel",
        "video": "Video"
    }
}

# ===== KEYBOARDS =====
def kb_main(lang):
    t = TEXTS[lang]
    return ReplyKeyboardMarkup([[t["catalog"], t["contact"], t["location"]]], resize_keyboard=True)

def kb_catalog(lang):
    t = TEXTS[lang]
    return ReplyKeyboardMarkup([
        [t["kitchen"], t["bedroom"]],
        [t["other"], t["soft"]],
        [t["video"]],
        [t["back"]]
    ], resize_keyboard=True)

def kb_more(lang):
    t = TEXTS[lang]
    return ReplyKeyboardMarkup([[t["more"], t["back"]]], resize_keyboard=True)

def kb_yesno(lang):
    t = TEXTS[lang]
    return ReplyKeyboardMarkup([[t["yes"], t["no"]]], resize_keyboard=True)

def get_lang(u):
    return u.get("lang", "ru")

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите язык",
        reply_markup=ReplyKeyboardMarkup([["Узбекский 🇺🇿", "Русский 🇷🇺"]], resize_keyboard=True)
    )

# ===== HANDLER =====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    u = context.user_data

    if text == "Русский 🇷🇺":
        u.clear()
        u["lang"] = "ru"
        await update.message.reply_text(TEXTS["ru"]["menu"], reply_markup=kb_main("ru"))
        return

    if text == "Узбекский 🇺🇿":
        u.clear()
        u["lang"] = "uz"
        await update.message.reply_text(TEXTS["uz"]["menu"], reply_markup=kb_main("uz"))
        return

    lang = get_lang(u)
    t = TEXTS[lang]

    if text == t["catalog"]:
        await update.message.reply_text(t["catalog"], reply_markup=kb_catalog(lang))
        return

    if text == t["contact"]:
        await update.message.reply_text(ws.acell("F1").value or "-", reply_markup=kb_main(lang))
        return

    if text == t["location"]:
        await update.message.reply_text(ws.acell("G1").value or "-", reply_markup=kb_main(lang))
        return

    if text == t["yes"]:
        await update.message.reply_text(t["catalog"], reply_markup=kb_catalog(lang))
        return

    if text == t["no"]:
        await update.message.reply_text(t["menu"], reply_markup=kb_main(lang))
        return

    if text == t["back"]:
        await update.message.reply_text(t["menu"], reply_markup=kb_main(lang))
        return

    if text == t["more"]:
        await send_page(update, context, True)
        return

    mapping = {
        t["kitchen"]: ("A", "photo"),
        t["bedroom"]: ("B", "photo"),
        t["other"]: ("C", "photo"),
        t["video"]: ("D", "video"),
        t["soft"]: ("E", "photo"),
    }

    if text in mapping:
        col, typ = mapping[text]
        u["col"] = col
        u["type"] = typ
        u["idx"] = 1
        await send_page(update, context)
        return

# ===== CACHE SEND =====
async def send_cached(bot_method, chat_id, url, is_video=False):
    if url in CACHE:
        return await bot_method(chat_id, CACHE[url])

    msg = await bot_method(chat_id, url)

    try:
        if is_video:
            CACHE[url] = msg.video.file_id
        else:
            CACHE[url] = msg.photo[-1].file_id
    except:
        pass

    return msg

# ===== SEND PAGE =====
async def send_page(update: Update, context: ContextTypes.DEFAULT_TYPE, next_page=False):
    u = context.user_data
    lang = get_lang(u)
    t = TEXTS[lang]

    col = u.get("col")
    typ = u.get("type", "photo")

    idx = u.get("idx", 1)
    if next_page:
        idx += 10

    values = ws.col_values(ord(col) - 64)

    items = []
    for i in range(idx - 1, min(idx + 9, len(values))):
        url = convert_drive_url(values[i].strip())
        if url:
            items.append(url)

    if not items:
        await update.message.reply_text(t["finished"], reply_markup=kb_yesno(lang))
        return

    u["idx"] = idx

    # 🔥 УБИРАЕМ КЛАВИАТУРУ
    await update.message.reply_text("...", reply_markup=ReplyKeyboardRemove())

    for url in items:
        try:
            if typ == "video":
                await send_cached(context.bot.send_video, update.effective_chat.id, url, True)
            else:
                await send_cached(context.bot.send_photo, update.effective_chat.id, url)

            await asyncio.sleep(0.3)

        except Exception as e:
            print("ERROR:", e)

    # 🔥 ПОСЛЕ 10 ШТУК ПОКАЗЫВАЕМ КНОПКИ
    if idx + 10 <= len(values):
        await update.message.reply_text(t["next"], reply_markup=kb_more(lang))
    else:
        await update.message.reply_text(t["finished"], reply_markup=kb_yesno(lang))

# ===== WEBHOOK =====
async def handle(request):
    data = await request.json()
    update = Update.de_json(data, request.app["bot"])
    await request.app["app"].process_update(update)
    return web.Response()

# ===== MAIN =====
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    await app.initialize()
    await app.start()

    await app.bot.set_webhook(WEBHOOK_URL + "/" + BOT_TOKEN)

    aio = web.Application()
    aio["bot"] = app.bot
    aio["app"] = app
    aio.router.add_post(f"/{BOT_TOKEN}", handle)

    runner = web.AppRunner(aio)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
