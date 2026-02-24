import os
import threading
import psycopg2
from flask import Flask, send_from_directory
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
WEBAPP_URL = os.environ.get("WEBAPP_URL")

# ================= DATABASE =================
def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id SERIAL PRIMARY KEY,
            barcode TEXT,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# ================= FLASK WEB SERVER =================
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
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Silakan scan barcode:",
        reply_markup=reply_markup
    )

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.web_app_data:
        barcode = update.message.web_app_data.data

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO scans (barcode) VALUES (%s)", (barcode,))
        conn.commit()
        cur.close()
        conn.close()

        await update.message.reply_text(f"✅ Barcode diterima: {barcode}")

def run_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        telegram.ext.MessageHandler(
            telegram.ext.filters.StatusUpdate.WEB_APP_DATA,
            handle_webapp_data
        )
    )
    application.run_polling()

# ================= MAIN =================
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_web).start()
    run_bot()
