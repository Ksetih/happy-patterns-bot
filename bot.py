from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN", "").strip()

print("TOKEN exists:", bool(TOKEN))
print("TOKEN length:", len(TOKEN))
print("TOKEN has colon:", ":" in TOKEN)
print("TOKEN starts with:", TOKEN[:4])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm JoyMap.\n\n"
        "Soon I'll help you discover what makes you happier."
    )


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.run_polling()
