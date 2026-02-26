import os
import psycopg2
import csv
from datetime import datetime, date
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

PILIH_LOKASI, PILIH_PIC, CARI_PRODUK, PILIH_PRODUK, INPUT_EXPIRED, TAMBAH_LAGI = range(6)

# ================= DATABASE =================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

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

def get_today_expired():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT nama_produk, expired_date
        FROM expired_logs
        WHERE (tanggal_input AT TIME ZONE 'Asia/Jakarta')::date
        = (NOW() AT TIME ZONE 'Asia/Jakarta')::date
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_monthly_report(year, month):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT nama_produk, expired_date, pic, tanggal_input
        FROM expired_logs
        WHERE EXTRACT(YEAR FROM tanggal_input)=%s
        AND EXTRACT(MONTH FROM tanggal_input)=%s
        ORDER BY tanggal_input
    """,(year,month))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ================= MENU =================

def main_menu():
    keyboard = [
        [KeyboardButton("📄 Export Harian")],
        [KeyboardButton("📊 Rekap Bulanan CSV")],
        [KeyboardButton("🗑 Hapus Item")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot Expired Aktif ✅",
        reply_markup=main_menu()
    )

# ================= EXPORT =================

async def export_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_today_expired()

    if not data:
        await update.message.reply_text("Tidak ada data hari ini.")
        return

    filename = "export_harian.txt"

    with open(filename, "w", encoding="utf-8") as f:
        for row in data:
            f.write(f"{row[0]} | {row[1]}\n")

    with open(filename, "rb") as f:
        await update.message.reply_document(f)

    os.remove(filename)

async def export_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    data = get_monthly_report(now.year, now.month)

    if not data:
        await update.message.reply_text("Tidak ada data bulan ini.")
        return

    filename = "rekap_bulanan.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Produk","Expired","PIC","Tanggal Input"])

        for row in data:
            writer.writerow(row)

    with open(filename, "rb") as f:
        await update.message.reply_document(f)

    os.remove(filename)

# ================= HAPUS =================

async def hapus_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_recent_logs()

    if not data:
        await update.message.reply_text("Tidak ada data.")
        return

    keyboard = []
    for row in data:
        id_, nama, expired = row
        keyboard.append([
            InlineKeyboardButton(f"{nama} | {expired}", callback_data=f"hapus_{id_}")
        ])

    await update.message.reply_text(
        "Pilih item yang ingin dihapus:",
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

    await query.edit_message_text("Item berhasil dihapus ✅")

# ================= MAIN =================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^📄 Export Harian$"), export_harian))
    app.add_handler(MessageHandler(filters.Regex("^📊 Rekap Bulanan CSV$"), export_bulanan))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Hapus Item$"), hapus_item_start))
    app.add_handler(CallbackQueryHandler(hapus_konfirmasi, pattern="^hapus_"))

    print("✅ BOT RUNNING STABLE")
    app.run_polling()
