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

PILIH_LOKASI, PILIH_PIC, CARI_PRODUK, PILIH_PRODUK, INPUT_EXPIRED = range(5)

# ================= DATABASE =================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def user_exists(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT nama FROM users
        WHERE telegram_id = %s AND is_active = true
    """, (telegram_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def get_locations():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nama_lokasi
        FROM locations
        WHERE is_active = true
        ORDER BY id
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_active_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nama
        FROM users
        WHERE is_active = true
        ORDER BY nama
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def search_product(keyword):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT upc, sku, deskripsi
        FROM products
        WHERE
            upc ILIKE %s OR
            sku::text ILIKE %s OR
            deskripsi ILIKE %s
        LIMIT 10
    """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"upc": r[0], "sku": r[1], "nama_produk": r[2]} for r in rows]

def save_expired(lokasi_id, upc, nama_produk, expired_date, pic):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expired_logs
        (tanggal_input, lokasi, upc, nama_produk, expired_date, pic)
        VALUES (NOW(), %s, %s, %s, %s, %s)
    """, (lokasi_id, upc, nama_produk, expired_date, pic))
    conn.commit()
    cur.close()
    conn.close()

def get_today_expired():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.nama_lokasi, p.sku, e.nama_produk,
               e.upc, e.expired_date, e.pic
        FROM expired_logs e
        LEFT JOIN locations l ON l.id::text = e.lokasi::text
        LEFT JOIN products p ON p.upc::text = e.upc::text
        WHERE DATE(e.tanggal_input) = CURRENT_DATE
        ORDER BY l.nama_lokasi, p.sku
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_monthly_report(year, month):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.nama_lokasi, p.sku, e.nama_produk,
               e.upc, e.expired_date, e.pic, e.tanggal_input
        FROM expired_logs e
        LEFT JOIN locations l ON l.id::text = e.lokasi::text
        LEFT JOIN products p ON p.upc::text = e.upc::text
        WHERE EXTRACT(YEAR FROM e.tanggal_input)=%s
          AND EXTRACT(MONTH FROM e.tanggal_input)=%s
        ORDER BY e.tanggal_input
    """, (year, month))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ================= MENU =================

def main_menu():
    keyboard = [
        [KeyboardButton("➕ Input Produk"), KeyboardButton("🔄 Pindah Lokasi")],
        [KeyboardButton("📄 Export Harian"), KeyboardButton("📊 Rekap Bulanan CSV")],
        [KeyboardButton("ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

cancel_button = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Batal", callback_data="batal")]]
)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_exists(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Anda tidak terdaftar.")
        return
    await update.message.reply_text(
        f"Halo {user[0]} 👋\nSilakan pilih menu:",
        reply_markup=main_menu()
    )

async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Proses dibatalkan.")
    await query.message.reply_text("Kembali ke menu:", reply_markup=main_menu())
    return ConversationHandler.END

# ================= EXPORT HARIAN =================

async def export_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_today_expired()
    if not data:
        await update.message.reply_text("Tidak ada data hari ini.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"expired_{today}.txt"

    lines = []
    lines.append(f"LAPORAN EXPIRED - {today}")
    lines.append("=" * 50)

    for row in data:
        lokasi, sku, produk, upc, expired, pic = row

        expired_date = expired
        status = ""
        selisih = (expired_date - date.today()).days

        if selisih < 0:
            status = "⚠️ SUDAH EXPIRED"
        elif selisih <= 3:
            status = "⚠️ SEGERA EXPIRED"

        lines.append(f"Lokasi : {lokasi}")
        lines.append(f"SKU    : {sku}")
        lines.append(f"Produk : {produk}")
        lines.append(f"UPC    : {upc}")
        lines.append(f"Expired: {expired} {status}")
        lines.append(f"PIC    : {pic}")
        lines.append("-" * 50)

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with open(filename, "rb") as f:
        await update.message.reply_document(f)

    os.remove(filename)

# ================= EXPORT BULANAN CSV =================

async def export_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    data = get_monthly_report(now.year, now.month)

    if not data:
        await update.message.reply_text("Tidak ada data bulan ini.")
        return

    filename = f"rekap_{now.year}_{now.month}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Lokasi","SKU","Produk","UPC","Expired","PIC","Tanggal Input"])
        for row in data:
            writer.writerow(row)

    with open(filename, "rb") as f:
        await update.message.reply_document(f)

    os.remove(filename)

# ================= MAIN =================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(batal, pattern="^batal$"))
    app.add_handler(MessageHandler(filters.Regex("^📄 Export Harian$"), export_harian))
    app.add_handler(MessageHandler(filters.Regex("^📊 Rekap Bulanan CSV$"), export_bulanan))

    print("✅ BOT PRO RUNNING...")
    app.run_polling()
