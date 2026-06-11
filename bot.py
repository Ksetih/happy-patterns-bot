import os
import csv
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "").strip()
CSV_FILE = "entries.csv"
USER_STATE = {}

def score_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(str(i), callback_data=f"score_{i}") for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=f"score_{i}") for i in range(6, 11)],
    ])

def save_entry(user, data):
    file_exists = os.path.exists(CSV_FILE)
    created_at = datetime.utcnow().isoformat()

    with open
