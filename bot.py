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

QUESTIONS = ["good", "anxiety", "goals"]

TEXTS = {
    "ru": {
        "lang_saved": "Готово, язык сохранён 🇷🇺\n\nНапиши /today, чтобы сделать первую запись.",
        "good": "😊 Что хорошего произошло сегодня?",
        "anxiety": "😟 Что сегодня тревожило или расстраивало?",
        "goals": "🎯 Что сегодня сделала для важных целей?",
        "score": "⭐ Оцени день от 1 до 10.",
        "next": "Дальше",
        "saved_item": "Записала. Можешь добавить ещё или перейти дальше.",
        "saved_all": "✨ Запись сохранена!\n\nСпасибо. Сегодняшний день уже не потерялся 🌱",
        "need_number": "Напиши число от 1 до 10.",
    },
    "en": {
        "lang_saved": "Done, language saved 🇬🇧\n\nSend /today to make your first entry.",
        "good": "😊 What good happened today?",
        "anxiety": "😟 What made you anxious or upset today?",
        "goals": "🎯 What did you do for your important goals today?",
        "score": "⭐ Rate your day from 1 to 10.",
        "next": "Next",
        "saved_item": "Saved. You can add one more or move next.",
        "saved_all": "✨ Entry saved!\n\nThank you. This day is no longer lost 🌱",
        "need_number": "Please send a number from 1 to 10.",
    },
}


def get_lang(user_id):
    return USER_LANG.get(user_id, "en")


def next_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(TEXTS[lang]["next"], callback_data="next")]
    ])


def save_rows(user_id, username, lang, data):
    file_exists = os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "created_at", "user_id", "username", "language",
                "block", "answer_index", "answer", "day_score"
            ])

        created_at = datetime.utcnow().isoformat()

        for block in QUESTIONS:
            for i, answer in enumerate(data.get(block, []), start=1):
                writer.writerow([
                    created_at, user_id, username or "", lang,
                    block, i, answer, ""
                ])

        writer.writerow([
            created_at, user_id, username or "", lang,
            "score", 1, "", data.get("score", "")
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

    USER_STATE[user_id] = {
        "step": "good",
        "data": {
            "good": [],
            "anxiety": [],
            "goals": [],
        }
    }

    await update.message.reply_text(TEXTS[lang]["good"])


async def go_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = get_lang(user_id)

    state = USER_STATE.get(user_id)
    if not state:
        await query.message.reply_text("Напиши /today.")
        return

    step = state["step"]

    if step == "good":
        state["step"] = "anxiety"
        await query.message.reply_text(TEXTS[lang]["anxiety"])
        return

    if step == "anxiety":
        state["step"] = "goals"
        await query.message.reply_text(TEXTS[lang]["goals"])
        return

    if step == "goals":
        state["step"] = "score"
        await query.message.reply_text(TEXTS[lang]["score"])
        return


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = get_lang(user_id)

    state = USER_STATE.get(user_id)

    if not state:
        await update.message.reply_text("Напиши /today, чтобы сделать запись.")
        return

    step = state["step"]
    text = update.message.text.strip()

    if step == "score":
        if not text.isdigit() or not (1 <= int(text) <= 10):
            await update.message.reply_text(TEXTS[lang]["need_number"])
            return

        state["data"]["score"] = int(text)

        save_rows(
            user_id=user_id,
            username=user.username,
            lang=lang,
            data=state["data"],
        )

        USER_STATE.pop(user_id, None)

        await update.message.reply_text(TEXTS[lang]["saved_all"])
        return

    state["data"][step].append(text)

    if len(state["data"][step]) >= 3:
        if step == "good":
            state["step"] = "anxiety"
            await update.message.reply_text(TEXTS[lang]["anxiety"])
        elif step == "anxiety":
            state["step"] = "goals"
            await update.message.reply_text(TEXTS[lang]["goals"])
        elif step == "goals":
            state["step"] = "score"
            await update.message.reply_text(TEXTS[lang]["score"])
        return

    await update.message.reply_text(
        TEXTS[lang]["saved_item"],
        reply_markup=next_keyboard(lang),
    )


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today))
app.add_handler(CallbackQueryHandler(choose_language, pattern="^lang_"))
app.add_handler(CallbackQueryHandler(go_next, pattern="^next$"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
