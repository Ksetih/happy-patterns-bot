import csv
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
CSV_FILE = "entries.csv"

USER_LANG = {}
USER_STATE = {}

BLOCKS = ["good", "anxiety", "goals"]

TEXTS = {
    "ru": {
        "choose_lang": "Выбери язык / Choose language:",
        "lang_saved": "Готово, язык сохранён 🇷🇺\n\nНапиши /today, чтобы сделать запись.",
        "good": "😊 Что хорошего произошло сегодня?",
        "anxiety": "😟 Что сегодня тревожило или расстраивало?",
        "goals": "🎯 Что сегодня сделала для важных целей?",
        "add_more": "➕ Добавить ещё",
        "next": "➡️ Следующий вопрос",
        "saved_one": "Записала ✅",
        "max_saved": "Записала 3 пункта ✅",
        "score": "⭐ Оцени день от 1 до 10.",
        "saved_all": "✨ Запись сохранена!",
        "start_today": "Напиши /today, чтобы сделать запись.",
    },
    "en": {
        "choose_lang": "Choose language / Выбери язык:",
        "lang_saved": "Done, language saved 🇬🇧\n\nSend /today to make an entry.",
        "good": "😊 What good happened today?",
        "anxiety": "😟 What made you anxious or upset today?",
        "goals": "🎯 What did you do for your important goals today?",
        "add_more": "➕ Add more",
        "next": "➡️ Next question",
        "saved_one": "Saved ✅",
        "max_saved": "Saved 3 items ✅",
        "score": "⭐ Rate your day from 1 to 10.",
        "saved_all": "✨ Entry saved!",
        "start_today": "Send /today to make an entry.",
    },
}


def get_lang(user_id: int) -> str:
    return USER_LANG.get(user_id, "en")


def actions_keyboard(lang: str, allow_more: bool = True):
    buttons = []
    if allow_more:
        buttons.append(InlineKeyboardButton(TEXTS[lang]["add_more"], callback_data="add_more"))
    buttons.append(InlineKeyboardButton(TEXTS[lang]["next"], callback_data="next"))
    return InlineKeyboardMarkup([buttons])


def score_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(str(i), callback_data=f"score_{i}") for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=f"score_{i}") for i in range(6, 11)],
    ])


def save_entry(user_id: int, username: str, lang: str, data: dict):
    file_exists = os.path.exists(CSV_FILE)
    created_at = datetime.utcnow().isoformat()

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "created_at", "user_id", "username", "language",
                "block", "answer_index", "answer", "day_score"
            ])

        for block in BLOCKS:
            for idx, answer in enumerate(data.get(block, []), start=1):
                writer.writerow([
                    created_at, user_id, username or "", lang,
                    block, idx, answer, ""
                ])

        writer.writerow([
            created_at, user_id, username or "", lang,
            "score", 1, "", data.get("score", "")
        ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
    ]])

    await update.message.reply_text(
        TEXTS["en"]["choose_lang"],
        reply_markup=keyboard,
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
        "data": {"good": [], "anxiety": [], "goals": [], "score": None},
        "waiting_for_text": True,
    }

    await update.message.reply_text(TEXTS[lang]["good"])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = get_lang(user_id)

    state = USER_STATE.get(user_id)
    if not state:
        await update.message.reply_text(TEXTS[lang]["start_today"])
        return

    step = state["step"]

    if step not in BLOCKS:
        await update.message.reply_text(TEXTS[lang]["score"], reply_markup=score_keyboard())
        return

    answer = update.message.text.strip()
    if not answer:
        return

    state["data"][step].append(answer)
    count = len(state["data"][step])

    if count >= 3:
        await update.message.reply_text(
            TEXTS[lang]["max_saved"],
            reply_markup=actions_keyboard(lang, allow_more=False),
        )
    else:
        await update.message.reply_text(
            TEXTS[lang]["saved_one"],
            reply_markup=actions_keyboard(lang, allow_more=True),
        )


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = get_lang(user_id)
    state = USER_STATE.get(user_id)

    if not state:
        await query.message.reply_text(TEXTS[lang]["start_today"])
        return

    action = query.data
    step = state["step"]

    if action == "add_more":
        await query.message.reply_text(TEXTS[lang][step])
        return

    if action == "next":
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
            await query.message.reply_text(TEXTS[lang]["score"], reply_markup=score_keyboard())
            return


async def handle_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    lang = get_lang(user_id)
    state = USER_STATE.get(user_id)

    if not state:
        await query.message.reply_text(TEXTS[lang]["start_today"])
        return

    score = int(query.data.replace("score_", ""))
    state["data"]["score"] = score

    save_entry(
        user_id=user_id,
        username=user.username,
        lang=lang,
        data=state["data"],
    )

    USER_STATE.pop(user_id, None)

    data = state["data"]
    summary = (
        f"{TEXTS[lang]['saved_all']}\n\n"
        f"😊 {len(data['good'])}\n"
        f"😟 {len(data['anxiety'])}\n"
        f"🎯 {len(data['goals'])}\n"
        f"⭐ {score}/10"
    )

    await query.message.reply_text(summary)


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today))
app.add_handler(CallbackQueryHandler(choose_language, pattern="^lang_"))
app.add_handler(CallbackQueryHandler(handle_score, pattern="^score_"))
app.add_handler(CallbackQueryHandler(handle_action, pattern="^(add_more|next)$"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
