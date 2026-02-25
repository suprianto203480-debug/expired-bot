import os
import psycopg2
from datetime import datetime
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
        SELECT 
            l.nama_lokasi,
            p.sku,
            e.nama_produk,
            e.upc,
            e.expired_date,
            e.pic
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

# ================= MENU =================

def main_menu():
    keyboard = [
        [KeyboardButton("➕ Input Produk"), KeyboardButton("🔄 Pindah Lokasi")],
        [KeyboardButton("📄 Export TXT"), KeyboardButton("ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = user_exists(telegram_id)

    if not user:
        await update.message.reply_text("❌ Anda tidak terdaftar.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"Halo {user[0]} 👋\n\nSilakan pilih menu:",
        reply_markup=main_menu()
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text in ["➕ Input Produk", "🔄 Pindah Lokasi"]:
        locations = get_locations()
        keyboard = [
            [InlineKeyboardButton(f"📍 {l[1]}", callback_data=f"lokasi_{l[0]}")]
            for l in locations
        ]

        await update.message.reply_text(
            "Pilih Lokasi:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PILIH_LOKASI

    if text == "📄 Export TXT":
        await export_txt(update, context)
        return ConversationHandler.END

    if text == "ℹ️ Help":
        await update.message.reply_text(
            "📌 MENU BOT:\n\n"
            "➕ Input Produk → tambah expired\n"
            "🔄 Pindah Lokasi → ganti lokasi\n"
            "📄 Export TXT → download laporan hari ini\n",
            reply_markup=main_menu()
        )

async def pilih_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lokasi_id = query.data.split("_")[1]
    context.user_data["lokasi"] = lokasi_id

    users = get_active_users()
    keyboard = [
        [InlineKeyboardButton(f"👤 {u[1]}", callback_data=f"pic_{u[0]}")]
        for u in users
    ]

    await query.edit_message_text(
        "Pilih PIC:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PILIH_PIC

async def pilih_pic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pic_id = query.data.split("_")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nama FROM users WHERE id=%s", (pic_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    context.user_data["pic"] = result[0]

    await query.edit_message_text(
        f"✅ PIC: {result[0]}\n\nKetik SKU / Nama / UPC:"
    )
    return CARI_PRODUK

async def cari_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    results = search_product(keyword)

    if not results:
        await update.message.reply_text("❌ Produk tidak ditemukan.")
        return CARI_PRODUK

    keyboard = [
        [InlineKeyboardButton(p["nama_produk"], callback_data=f"produk_{p['upc']}")]
        for p in results
    ]

    context.user_data["last_results"] = results

    await update.message.reply_text(
        "Pilih Produk:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PILIH_PRODUK

async def pilih_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    upc = query.data.split("_")[1]
    selected = next(
        (p for p in context.user_data["last_results"] if p["upc"] == upc),
        None
    )

    context.user_data["selected_product"] = selected

    await query.edit_message_text(
        f"Produk: {selected['nama_produk']}\nMasukkan tanggal expired (YYYY-MM-DD):"
    )
    return INPUT_EXPIRED

async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expired_date = update.message.text.strip()

    try:
        datetime.strptime(expired_date, "%Y-%m-%d")
    except:
        await update.message.reply_text("❌ Format salah. Gunakan YYYY-MM-DD")
        return INPUT_EXPIRED

    produk = context.user_data["selected_product"]
    lokasi = context.user_data["lokasi"]
    pic = context.user_data["pic"]

    save_expired(lokasi, produk["upc"], produk["nama_produk"], expired_date, pic)

    await update.message.reply_text(
        "✅ Data berhasil disimpan.",
        reply_markup=main_menu()
    )

    return ConversationHandler.END

# ================= EXPORT =================

async def export_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_today_expired()

    if not data:
        await update.message.reply_text("❌ Tidak ada data expired hari ini.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"expired_{today}.txt"

    lines = []
    lines.append(f"LAPORAN EXPIRED - {today}")
    lines.append("=" * 40)

    for row in data:
        lokasi, sku, produk, upc, expired, pic = row
        lines.append(f"Lokasi : {lokasi}")
        lines.append(f"SKU    : {sku}")
        lines.append(f"Produk : {produk}")
        lines.append(f"UPC    : {upc}")
        lines.append(f"Expired: {expired}")
        lines.append(f"PIC    : {pic}")
        lines.append("-" * 40)

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with open(filename, "rb") as f:
        await update.message.reply_document(document=f)

    os.remove(filename)

# ================= MAIN =================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(➕ Input Produk|🔄 Pindah Lokasi)$"), menu_handler)],
        states={
            PILIH_LOKASI: [CallbackQueryHandler(pilih_lokasi, pattern="^lokasi_")],
            PILIH_PIC: [CallbackQueryHandler(pilih_pic, pattern="^pic_")],
            CARI_PRODUK: [MessageHandler(filters.TEXT & ~filters.COMMAND, cari_produk)],
            PILIH_PRODUK: [CallbackQueryHandler(pilih_produk, pattern="^produk_")],
            INPUT_EXPIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_expired)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))
    app.add_handler(CommandHandler("export", export_txt))

    print("✅ Bot Running...")
    app.run_polling()

