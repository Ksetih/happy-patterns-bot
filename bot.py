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
ENTRIES_FILE = "entries.csv"

USER_STATE = {}
BLOCKS = ["good", "anxiety", "goals"]

TEXTS = {
    "ru": {
        "start": "Привет! Я JoyMap 🌱\n\nНапиши /today, чтобы сделать запись.",
        "start_today": "Напиши /today, чтобы сделать запись.",
        "good": "😊 Что хорошего произошло сегодня?",
        "anxiety": "😟 Что сегодня тревожило или расстраивало?",
        "goals": "🎯 Что сегодня сделала для важных целей?",
        "score": "⭐ Оцени день от 1 до 10.",
        "add_more": "➕ Добавить ещё",
        "next": "➡️ Следующий вопрос",
        "saved_one": "Записала ✅",
        "max_saved": "Записала 3 пункта ✅",
        "history_stub": "📅 История появится в следующей версии.",
        "stats_stub": "📊 Статистика появится в следующей версии.",
    },
    "en": {
        "start": "Hi! I'm JoyMap 🌱\n\nSend /today to make an entry.",
        "start_today": "Send /today to make an entry.",
        "good": "😊 What good happened today?",
        "anxiety": "😟 What made you anxious or upset today?",
        "goals": "🎯 What did you do for your important goals today?",
        "score": "⭐ Rate your day from 1 to 10.",
        "add_more": "➕ Add more",
        "next": "➡️ Next question",
        "saved_one": "Saved ✅",
        "max_saved": "Saved 3 items ✅",
        "history_stub": "📅 History will appear in the next version.",
        "stats_stub": "📊 Stats will appear in the next version.",
    },
}


def get_lang(user) -> str:
    code = getattr(user, "language_code", "") or ""
    if code.lower().startswith("ru"):
        return "ru"
    return "en"


def actions_keyboard(lang: str, allow_more: bool):
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


def final_keyboard(lang: str):
    if lang == "ru":
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("📅 История", callback_data="history"),
            InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        ]])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 History", callback_data="history"),
        InlineKeyboardButton("📊 Stats", callback_data="stats"),
    ]])


def save_entry(user_id: int, username: str, lang: str, data: dict):
    file_exists = os.path.exists(ENTRIES_FILE)
    created_at = datetime.utcnow().isoformat()

    with open(ENTRIES_FILE, "a", newline="", encoding="utf-8") as f:
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
            "score", 1, "", data.get("score")
        ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user)
    await update.message.reply_text(TEXTS[lang]["start"])


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(update.effective_user)

    USER_STATE[user_id] = {
        "step": "good",
        "data": {"good": [], "anxiety": [], "goals": [], "score": None},
    }

    await update.message.reply_text(TEXTS[lang]["good"])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = get_lang(user)

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

    user = query.from_user
    user_id = user.id
    lang = get_lang(user)

    state = USER_STATE.get(user_id)
    if not state:
        await query.message.reply_text(TEXTS[lang]["start_today"])
        return

    step = state["step"]

    if query.data == "add_more":
        await query.message.reply_text(TEXTS[lang][step])
        return

    if query.data == "next":
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
    lang = get_lang(user)

    state = USER_STATE.get(user_id)
    if not state:
        await query.message.reply_text(TEXTS[lang]["start_today"])
        return

    score = int(query.data.replace("score_", ""))
    state["data"]["score"] = score

    save_entry(user_id, user.username, lang, state["data"])

    data = state["data"]
    USER_STATE.pop(user_id, None)

    if lang == "ru":
        summary = (
            "✨ Запись сохранена!\n\n"
            "Сегодня:\n\n"
            f"😊 Хорошее — {len(data['good'])} пункт(а)\n"
            f"😟 Тревоги — {len(data['anxiety'])} пункт(а)\n"
            f"🎯 Цели — {len(data['goals'])} пункт(а)\n\n"
            f"Оценка дня: {score}/10"
        )
    else:
        summary = (
            "✨ Entry saved!\n\n"
            "Today:\n\n"
            f"😊 Good things — {len(data['good'])}\n"
            f"😟 Anxieties — {len(data['anxiety'])}\n"
            f"🎯 Goals — {len(data['goals'])}\n\n"
            f"Day rating: {score}/10"
        )

    await query.message.reply_text(summary, reply_markup=final_keyboard(lang))


async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user)
    await query.message.reply_text(TEXTS[lang]["history_stub"])


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(query.from_user)
    await query.message.reply_text(TEXTS[lang]["stats_stub"])


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today))

app.add_handler(CallbackQueryHandler(handle_score, pattern="^score_"))
app.add_handler(CallbackQueryHandler(handle_action, pattern="^(add_more|next)$"))
app.add_handler(CallbackQueryHandler(handle_history, pattern="^history$"))
app.add_handler(CallbackQueryHandler(handle_stats, pattern="^stats$"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
