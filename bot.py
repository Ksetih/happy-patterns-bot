import csv
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

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

ADMIN_ID = 64474188

ENTRIES_FILE = "entries.csv"
STATE_FILE = "state.json"
USERS_FILE = "users.json"

LOCAL_TZ = ZoneInfo("Europe/Moscow")
REMINDER_TIME = time(hour=23, minute=0, tzinfo=LOCAL_TZ)

BLOCKS = ["good", "anxiety", "goals"]


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


USER_STATE = load_state()


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)


USERS = load_users()


def user_key(user_id):
    return str(user_id)


def get_user_state(user_id):
    return USER_STATE.get(user_key(user_id))


def set_user_state(user_id, state):
    USER_STATE[user_key(user_id)] = state
    save_state(USER_STATE)


def clear_user_state(user_id):
    USER_STATE.pop(user_key(user_id), None)
    save_state(USER_STATE)


def remember_user(user):
    if not user:
        return

    USERS[user_key(user.id)] = {
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
    }
    save_users(USERS)


def actions_keyboard(allow_more=True):
    buttons = []
    if allow_more:
        buttons.append(InlineKeyboardButton("➕ Добавить ещё", callback_data="add_more"))
    buttons.append(InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next"))
    return InlineKeyboardMarkup([buttons])


def score_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(str(i), callback_data=f"score_{i}") for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=f"score_{i}") for i in range(6, 11)],
    ])


def final_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 История", callback_data="history"),
        InlineKeyboardButton("🗺 Карта радости", callback_data="joymap"),
    ]])


def local_today():
    return datetime.now(LOCAL_TZ).date()


def parse_entry_date(created_at):
    try:
        entry_time = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return None

    if entry_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=ZoneInfo("UTC"))

    return entry_time.astimezone(LOCAL_TZ).date()


def user_completed_today(user_id):
    if not os.path.exists(ENTRIES_FILE):
        return False

    today = local_today()
    user_id = str(user_id)

    with open(ENTRIES_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("user_id") != user_id:
                continue
            if row.get("block") != "score":
                continue
            if parse_entry_date(row.get("created_at")) == today:
                return True

    return False


def save_entry(user, data):
    file_exists = os.path.exists(ENTRIES_FILE)
    created_at = datetime.now(ZoneInfo("UTC")).isoformat()

    with open(ENTRIES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "created_at",
                "user_id",
                "username",
                "block",
                "answer_index",
                "answer",
                "day_score",
            ])

        for block in BLOCKS:
            for idx, answer in enumerate(data.get(block, []), start=1):
                writer.writerow([
                    created_at,
                    user.id,
                    user.username or "",
                    block,
                    idx,
                    answer,
                    "",
                ])

        writer.writerow([
            created_at,
            user.id,
            user.username or "",
            "score",
            1,
            "",
            data.get("score"),
        ])


def get_admin_stats():
    if not os.path.exists(ENTRIES_FILE):
        return {
            "users": 0,
            "completed_entries": 0,
            "total_rows": 0,
            "good_rows": 0,
            "anxiety_rows": 0,
            "goals_rows": 0,
        }

    users = set()
    completed_entries = 0
    total_rows = 0
    good_rows = 0
    anxiety_rows = 0
    goals_rows = 0

    with open(ENTRIES_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            total_rows += 1
            users.add(row["user_id"])

            if row["block"] == "score":
                completed_entries += 1
            elif row["block"] == "good":
                good_rows += 1
            elif row["block"] == "anxiety":
                anxiety_rows += 1
            elif row["block"] == "goals":
                goals_rows += 1

    return {
        "users": len(users),
        "completed_entries": completed_entries,
        "total_rows": total_rows,
        "good_rows": good_rows,
        "anxiety_rows": anxiety_rows,
        "goals_rows": goals_rows,
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(update.effective_user)

    await update.message.reply_text(
        "Привет! Я JoyMap 🌱\n\n"
        "Я помогу тебе замечать, что делает твои дни лучше.\n\n"
        "Напиши /today, чтобы сделать первую запись."
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(update.effective_user)

    user_id = update.effective_user.id

    state = {
        "step": "good",
        "data": {
            "good": [],
            "anxiety": [],
            "goals": [],
            "score": None,
        },
    }

    set_user_state(user_id, state)

    await update.message.reply_text("😊 Что хорошего произошло сегодня?")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(update.effective_user)

    clear_user_state(update.effective_user.id)
    await update.message.reply_text("Сбросила текущую запись. Можно начать заново: /today")


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(update.effective_user)

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Команда недоступна.")
        return

    stats = get_admin_stats()

    await update.message.reply_text(
        "📊 Admin stats\n\n"
        f"Уникальных пользователей с записями: {stats['users']}\n"
        f"Завершённых дневников: {stats['completed_entries']}\n"
        f"Всего сохранённых строк: {stats['total_rows']}\n\n"
        f"😊 Хорошее: {stats['good_rows']}\n"
        f"😟 Тревоги: {stats['anxiety_rows']}\n"
        f"🎯 Цели: {stats['goals_rows']}"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    remember_user(user)

    user_id = user.id

    state = get_user_state(user_id)

    if not state:
        await update.message.reply_text("Напиши /today, чтобы сделать запись.")
        return

    step = state["step"]

    if step not in BLOCKS:
        await update.message.reply_text(
            "⭐ Оцени день от 1 до 10.",
            reply_markup=score_keyboard(),
        )
        return

    answer = update.message.text.strip()
    if not answer:
        return

    state["data"][step].append(answer)
    count = len(state["data"][step])

    set_user_state(user_id, state)

    if count >= 3:
        await update.message.reply_text(
            "Записала 3 пункта ✅",
            reply_markup=actions_keyboard(allow_more=False),
        )
    else:
        await update.message.reply_text(
            "Записала ✅",
            reply_markup=actions_keyboard(allow_more=True),
        )


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    remember_user(query.from_user)

    await query.answer()

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_id = query.from_user.id
    state = get_user_state(user_id)

    if not state:
        await query.message.reply_text("Напиши /today, чтобы сделать запись.")
        return

    step = state["step"]

    if query.data == "add_more":
        if step == "good":
            await query.message.reply_text("😊 Что ещё хорошего произошло сегодня?")
        elif step == "anxiety":
            await query.message.reply_text("😟 Что ещё тревожило или расстраивало?")
        elif step == "goals":
            await query.message.reply_text("🎯 Что ещё сделала для важных целей?")
        return

    if query.data == "next":
        if step == "good":
            state["step"] = "anxiety"
            set_user_state(user_id, state)
            await query.message.reply_text("😟 Что сегодня тревожило или расстраивало?")
            return

        if step == "anxiety":
            state["step"] = "goals"
            set_user_state(user_id, state)
            await query.message.reply_text("🎯 Что сегодня сделала для важных целей?")
            return

        if step == "goals":
            state["step"] = "score"
            set_user_state(user_id, state)
            await query.message.reply_text(
                "⭐ Оцени день от 1 до 10.",
                reply_markup=score_keyboard(),
            )
            return


async def handle_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    remember_user(query.from_user)

    await query.answer()

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    user = query.from_user
    user_id = user.id

    state = get_user_state(user_id)

    if not state:
        await query.message.reply_text("Напиши /today, чтобы сделать запись.")
        return

    score = int(query.data.replace("score_", ""))

    state["data"]["score"] = score
    save_entry(user, state["data"])

    data = state["data"]
    clear_user_state(user_id)

    summary = (
        "✨ Первая запись сохранена\n\n"
        "Это первая точка на твоей карте радости 🌱\n\n"
        "Каждый день состоит из сотен событий, но мозг чаще запоминает проблемы.\n\n"
        "Сегодня ты заметила:\n\n"
        f"😊 {len(data['good'])} хороших события\n"
        f"🎯 {len(data['goals'])} шага к важным целям\n\n"
        "Возвращайся завтра и мы начнём находить закономерности "
        "и понимать, что делает твои дни счастливее. ✨"
    )

    await query.message.reply_text(summary, reply_markup=final_keyboard())


async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text("📅 Скоро здесь появится история твоих записей ✨")


async def handle_joymap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "🗺 Чтобы увидеть первые закономерности, нужно минимум 3 дня записей 🌱"
    )


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    for user_id in list(USERS.keys()):
        if user_completed_today(user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=(
                    "🌙 Напоминание\n\n"
                    "Заполни, что хорошего было сегодня.\n\n"
                    "Напиши /today, чтобы сделать запись."
                ),
            )
        except Exception:
            pass


app = Application.builder().token(TOKEN).build()

app.job_queue.run_daily(send_daily_reminders, time=REMINDER_TIME, name="daily_reminders")

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CommandHandler("admin", admin))

app.add_handler(CallbackQueryHandler(handle_score, pattern="^score_"))
app.add_handler(CallbackQueryHandler(handle_action, pattern="^(add_more|next)$"))
app.add_handler(CallbackQueryHandler(handle_history, pattern="^history$"))
app.add_handler(CallbackQueryHandler(handle_joymap, pattern="^joymap$"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
