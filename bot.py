from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import os
import csv
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN", "").strip()
USER_LANG = {}
USER_STATE = {}
CSV_FILE = "entries.csv"


TEXTS = {
    "ru": {
        "lang_saved": "Готово, язык сохранён 🇷🇺\n\nНапиши /today, чтобы сделать первую запись.",
        "today": "😊 Что хорошего произошло сегодня?\n\nНапиши до 3 пунктов, каждый с новой строки.",
        "saved": "✨ Сохранено!\n\nСегодня ты отметила:",
    },
    "en": {
        "lang_saved": "Done, language saved 🇬🇧\n\nSend /today to make your first entry.",
        "today": "😊 What good happened today?\n\nWrite up to 3 items, one per line.",
        "saved": "✨ Saved!\n\nToday you noticed:",
    },
}


def get_lang(user_id):
    return USER_LANG.get(user_id, "en")


def save_entries(user_id, username, lang, block, answers):
    file_exists = os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["created_at", "user_id", "username", "language", "block", "answer_index", "answer"])

        for i, answer in enumerate(answers, start=1):
            writer.writerow([
                datetime.utcnow().isoformat(),
                user_id,
                username or "",
                lang,
                block,
                i,
                answer,
            ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
    ]]

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

    USER_STATE[user_id] = "waiting_good"

    await update.message.reply_text(TEXTS[lang]["today"])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = get_lang(user_id)

    state = USER_STATE.get(user_id)

    if state != "waiting_good":
        await update.message.reply_text("Напиши /today, чтобы сделать запись.")
        return

    answers = [
        line.strip()
        for line in update.message.text.split("\n")
        if line.strip()
    ][:3]

    save_entries(
        user_id=user_id,
        username=user.username,
        lang=lang,
        block="good",
        answers=answers,
    )

    USER_STATE.pop(user_id, None)

    bullets = "\n".join([f"• {a}" for a in answers])
    await update.message.reply_text(f"{TEXTS[lang]['saved']}\n\n{bullets}")


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today))
app.add_handler(CallbackQueryHandler(choose_language))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
