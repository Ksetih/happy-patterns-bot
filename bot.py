from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import os

TOKEN = os.getenv("BOT_TOKEN", "").strip()

USER_LANG = {}


TEXTS = {
    "ru": {
        "welcome": "Привет! Я JoyMap 🌱\n\nЯ помогу тебе замечать, что делает жизнь лучше.",
        "choose_lang": "Выбери язык:",
        "lang_saved": "Готово, язык сохранён 🇷🇺\n\nНапиши /today, чтобы сделать первую запись.",
        "today": "😊 Что хорошего произошло сегодня?\n\nНапиши до 3 пунктов, каждый с новой строки.",
    },
    "en": {
        "welcome": "Hi! I'm JoyMap 🌱\n\nI'll help you discover what makes your life better.",
        "choose_lang": "Choose language:",
        "lang_saved": "Done, language saved 🇬🇧\n\nSend /today to make your first entry.",
        "today": "😊 What good happened today?\n\nWrite up to 3 items, one per line.",
    },
}


def get_lang(user_id):
    return USER_LANG.get(user_id, "en")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        ]
    ]

    await update.message.reply_text(
        "Choose language / Выбери язык:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = query.data.replace("lang_", "")

    USER_LANG[user_id] = lang

    await query.edit_message_text(TEXTS[lang]["lang_saved"])


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    await update.message.reply_text(TEXTS[lang]["today"])


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today))
app.add_handler(CallbackQueryHandler(choose_language))

app.run_polling()
