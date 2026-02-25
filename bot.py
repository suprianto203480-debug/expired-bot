import os
import psycopg2
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ================= DATABASE =================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def get_expired_products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nama_produk, expired_date
        FROM expired_logs
        WHERE expired_date < CURRENT_DATE
        ORDER BY expired_date
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def delete_expired_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expired_logs WHERE id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()

# ================= MENU =================

def main_menu():
    keyboard = [
        ["➕ Input Produk"],
        ["📄 Export Harian"],
        ["📊 Rekap Bulanan CSV"],
        ["🗑 Hapus Produk Expired"],
        ["ℹ️ Help"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 Monitoring Expired Produk",
        reply_markup=main_menu()
    )

# ================= HAPUS PRODUK =================

async def hapus_produk_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_expired_products()

    if not data:
        await update.message.reply_text("✅ Tidak ada produk expired.")
        return

    keyboard = []
    for row in data:
        product_id = row[0]
        nama = row[1]
        expired = row[2]
        text = f"{nama} | {expired}"
        keyboard.append([
            InlineKeyboardButton(text, callback_data=f"hapus_{product_id}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🗑 Pilih produk yang ingin dihapus:",
        reply_markup=reply_markup
    )

async def konfirmasi_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.split("_")[1]

    delete_expired_product(product_id)

    await query.edit_message_text("✅ Produk berhasil dihapus.")

# ================= HELP =================

async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Gunakan menu untuk mengelola produk expired."
    )

# ================= MAIN =================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Hapus Produk Expired$"), hapus_produk_expired))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"), help_menu))
    app.add_handler(CallbackQueryHandler(konfirmasi_hapus, pattern="^hapus_"))

    print("✅ BOT RUNNING STABLE")
    app.run_polling()
