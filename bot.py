import os
import threading
from flask import Flask, send_from_directory
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")

# ================= WEB SERVER =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running 🚀"

@app.route("/scanner")
def scanner():
    return send_from_directory(".", "scanner.html")

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================= TELEGRAM BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton(
            text="📷 Scan Barcode",
            web_app=WebAppInfo(url=os.environ.get("WEBAPP_URL"))
        )]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Silakan scan barcode:",
        reply_markup=reply_markup
    )

def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

# ================= RUN BOTH =================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
