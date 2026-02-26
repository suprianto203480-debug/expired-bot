import os
import psycopg2
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)

# ================== KONFIGURASI ==================
TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ================== STATE ==================
NAMA_PRODUK, TANGGAL_EXPIRED = range(2)

# ================== DATABASE ==================
def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expired_logs (
            id SERIAL PRIMARY KEY,
            nama_produk TEXT,
            expired_date DATE,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# ================== MENU ==================
def main_menu():
    keyboard = [
        ["➕ Tambah Produk"],
        ["🗑 Hapus Produk"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Bot Expired Monitoring Aktif",
        reply_markup=main_menu()
    )

# ================== TAMBAH PRODUK ==================
async def tambah_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Masukkan Nama Produk:")
    return NAMA_PRODUK

async def simpan_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nama_produk"] = update.message.text
    await update.message.reply_text("Masukkan Tanggal Expired (YYYY-MM-DD):")
    return TANGGAL_EXPIRED

async def simpan_tanggal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        expired_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
    except:
        await update.message.reply_text("Format salah! Gunakan YYYY-MM-DD")
        return TANGGAL_EXPIRED

    nama_produk = context.user_data["nama_produk"]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expired_logs (nama_produk, expired_date) VALUES (%s,%s)",
        (nama_produk, expired_date)
    )
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text("✅ Produk berhasil disimpan!", reply_markup=main_menu())
    return ConversationHandler.END

# ================== GET DATA TERBARU ==================
def get_recent_logs():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nama_produk, expired_date
        FROM expired_logs
        ORDER BY tanggal_input DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ================== HAPUS PRODUK ==================
async def hapus_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_recent_logs()

    if not data:
        await update.message.reply_text("Tidak ada data untuk dihapus.")
        return

    keyboard = []
    for row in data:
        id_, nama_produk, expired = row
        text = f"{nama_produk} | {expired}"
        keyboard.append([
            InlineKeyboardButton(text, callback_data=f"hapus_{id_}")
        ])

    await update.message.reply_text(
        "🗑 Pilih item yang ingin dihapus:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def hapus_konfirmasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_id = query.data.split("_")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expired_logs WHERE id=%s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()

    await query.edit_message_text("✅ Item berhasil dihapus.")

# ================== MAIN ==================
def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Tambah Produk$"), tambah_produk)],
        states={
            NAMA_PRODUK: [MessageHandler(filters.TEXT & ~filters.COMMAND, simpan_nama)],
            TANGGAL_EXPIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, simpan_tanggal)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^🗑 Hapus Produk$"), hapus_item_start))
    app.add_handler(CallbackQueryHandler(hapus_konfirmasi, pattern="^hapus_"))

    print("✅ BOT FINAL STABLE RUNNING")
    app.run_polling()

if __name__ == "__main__":
    main()
