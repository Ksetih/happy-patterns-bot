import csv
import json
import os
import re
from collections import Counter
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
ANALYTICS_MILESTONES = [3, 7, 14, 30]
MILESTONE_TITLES = {
    3: "Первые 3 дня",
    7: "Неделя",
    14: "2 недели",
    30: "Месяц",
}
STOP_WORDS = {
    "была",
    "было",
    "были",
    "быть",
    "все",
    "для",
    "день",
    "еще",
    "как",
    "меня",
    "мне",
    "мой",
    "моя",
    "мои",
    "она",
    "они",
    "очень",
    "при",
    "про",
    "себя",
    "сегодня",
    "так",
    "там",
    "тебя",
    "что",
    "это",
}


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


def get_user_daily_entries(user_id):
    if not os.path.exists(ENTRIES_FILE):
        return []

    user_id = str(user_id)
    entries_by_date = {}

    with open(ENTRIES_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("user_id") != user_id:
                continue

            entry_date = parse_entry_date(row.get("created_at"))
            if not entry_date:
                continue

            day_key = entry_date.isoformat()
            entry = entries_by_date.setdefault(day_key, {
                "date": entry_date,
                "good": [],
                "anxiety": [],
                "goals": [],
                "score": None,
            })

            block = row.get("block")
            if block in BLOCKS and row.get("answer"):
                entry[block].append(row["answer"])
            elif block == "score" and row.get("day_score"):
                try:
                    entry["score"] = int(row["day_score"])
                except ValueError:
                    pass

    completed_entries = [
        entry for entry in entries_by_date.values()
        if entry["score"] is not None
    ]
    return sorted(completed_entries, key=lambda item: item["date"])


def next_analytics_milestone(entries_count):
    for milestone in ANALYTICS_MILESTONES:
        if entries_count < milestone:
            return milestone
    return None


def best_available_milestone(entries_count):
    available = [
        milestone for milestone in ANALYTICS_MILESTONES
        if entries_count >= milestone
    ]
    if not available:
        return None
    return max(available)


def top_words(entries, block, limit=5):
    counter = Counter()

    for entry in entries:
        for answer in entry[block]:
            words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", answer.lower())
            for word in words:
                if len(word) < 4 or word in STOP_WORDS:
                    continue
                counter[word] += 1

    return [word for word, _ in counter.most_common(limit)]


def format_words(words):
    if not words:
        return "пока нет явных повторов"
    return ", ".join(words)


def build_analytics_message(user_id, milestone=None):
    entries = get_user_daily_entries(user_id)
    entries_count = len(entries)

    if milestone is None:
        milestone = best_available_milestone(entries_count)

    if milestone is None:
        next_milestone = next_analytics_milestone(entries_count)
        days_left = next_milestone - entries_count
        return (
            "🗺 Карта радости ещё собирается\n\n"
            f"Сейчас есть завершённых дней: {entries_count}.\n"
            f"До первой аналитики осталось: {days_left}."
        )

    period_entries = entries[-milestone:]
    scores = [entry["score"] for entry in period_entries]
    average_score = sum(scores) / len(scores)
    best_entry = max(period_entries, key=lambda entry: entry["score"])
    low_entry = min(period_entries, key=lambda entry: entry["score"])

    good_count = sum(len(entry["good"]) for entry in period_entries)
    anxiety_count = sum(len(entry["anxiety"]) for entry in period_entries)
    goals_count = sum(len(entry["goals"]) for entry in period_entries)

    next_milestone = next_analytics_milestone(entries_count)
    next_line = ""
    if next_milestone:
        next_line = (
            f"\n\nСледующая аналитика откроется на {next_milestone} днях."
        )

    return (
        f"🗺 {MILESTONE_TITLES[milestone]}: твоя аналитика\n\n"
        f"Завершённых дней всего: {entries_count}\n"
        f"В этом периоде: {milestone}\n"
        f"Средняя оценка дня: {average_score:.1f}/10\n"
        f"Лучший день: {best_entry['date'].strftime('%d.%m')} "
        f"({best_entry['score']}/10)\n"
        f"Самый сложный день: {low_entry['date'].strftime('%d.%m')} "
        f"({low_entry['score']}/10)\n\n"
        "Что чаще связано с хорошим:\n"
        f"😊 {format_words(top_words(period_entries, 'good'))}\n\n"
        "Что чаще тревожит:\n"
        f"😟 {format_words(top_words(period_entries, 'anxiety'))}\n\n"
        "Где чаще были шаги к целям:\n"
        f"🎯 {format_words(top_words(period_entries, 'goals'))}\n\n"
        "За период ты заметила:\n"
        f"😊 хорошего: {good_count}\n"
        f"😟 тревог: {anxiety_count}\n"
        f"🎯 шагов к целям: {goals_count}"
        f"{next_line}"
    )


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
        "Напиши /today, чтобы сделать первую запись.\n"
        "А /analytics покажет карту радости, когда накопится минимум 3 дня."
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


async def analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remember_user(update.effective_user)

    await update.message.reply_text(
        build_analytics_message(update.effective_user.id)
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

    entries_count = len(get_user_daily_entries(user_id))
    if entries_count in ANALYTICS_MILESTONES:
        await query.message.reply_text(
            build_analytics_message(user_id, milestone=entries_count)
        )


async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text("📅 Скоро здесь появится история твоих записей ✨")


async def handle_joymap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    remember_user(query.from_user)

    await query.answer()

    await query.message.reply_text(build_analytics_message(query.from_user.id))


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
app.add_handler(CommandHandler("analytics", analytics))

app.add_handler(CallbackQueryHandler(handle_score, pattern="^score_"))
app.add_handler(CallbackQueryHandler(handle_action, pattern="^(add_more|next)$"))
app.add_handler(CallbackQueryHandler(handle_history, pattern="^history$"))
app.add_handler(CallbackQueryHandler(handle_joymap, pattern="^joymap$"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
