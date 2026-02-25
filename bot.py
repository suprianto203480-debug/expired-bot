import os
import psycopg2
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
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

# ========================
# CONFIG
# ========================

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

PILIH_LOKASI, CARI_PRODUK, PILIH_PRODUK, INPUT_EXPIRED = range(4)

# ========================
# DATABASE CONNECTION
# ========================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

# ========================
# DATABASE FUNCTIONS
# ========================

def user_exists(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT nama FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def search_product(keyword):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT upc, nama_produk
        FROM products
        WHERE
            upc ILIKE %s OR
            sku ILIKE %s OR
            nama_produk ILIKE %s
        LIMIT 10
    """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [{"upc": r[0], "nama_produk": r[1]} for r in rows]

def save_expired(lokasi, upc, nama_produk, expired_date, pic):
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO expired_logs
            (tanggal_input, lokasi, upc, nama_produk, expired_date, pic)
            VALUES (NOW(), %s, %s, %s, %s, %s)
        """, (lokasi, upc, nama_produk, expired_date, pic))

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print("Insert Error:", e)
        return False

# ========================
# HANDLERS
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    user = user_exists(telegram_id)
    if not user:
        await update.message.reply_text("❌ Anda tidak terdaftar")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("📍 Lokasi 1", callback_data="lokasi_1")],
        [InlineKeyboardButton("📍 Lokasi 2", callback_data="lokasi_2")]
    ]

    await update.message.reply_text(
        f"Halo {user[0]} 👋\n\nPilih Lokasi:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return PILIH_LOKASI

# ========================
# PILIH LOKASI
# ========================

async def pilih_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lokasi = query.data.split("_")[1]
    context.user_data["lokasi"] = lokasi

    await query.edit_message_text(
        f"✅ Lokasi dipilih: {lokasi}\n\nKetik SKU / Nama / UPC produk:"
    )

    return CARI_PRODUK

# ========================
# CARI PRODUK
# ========================

async def cari_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text

    results = search_product(keyword)

    if not results:
        await update.message.reply_text("❌ Produk tidak ditemukan. Coba lagi.")
        return CARI_PRODUK

    keyboard = []

    for p in results:
        keyboard.append([
            InlineKeyboardButton(
                p["nama_produk"],
                callback_data=f"produk_{p['upc']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔁 Pindah Lokasi", callback_data="ganti_lokasi")
    ])

    await update.message.reply_text(
        "Pilih Produk:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    context.user_data["last_results"] = results
    return PILIH_PRODUK

# ========================
# PILIH PRODUK
# ========================

async def pilih_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ganti_lokasi":
        keyboard = [
            [InlineKeyboardButton("📍 Lokasi 1", callback_data="lokasi_1")],
            [InlineKeyboardButton("📍 Lokasi 2", callback_data="lokasi_2")]
        ]
        await query.edit_message_text(
            "Pilih Lokasi:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PILIH_LOKASI

    upc = query.data.split("_")[1]

    for p in context.user_data["last_results"]:
        if p["upc"] == upc:
            context.user_data["selected_product"] = p
            break

    await query.edit_message_text(
        f"Produk: {context.user_data['selected_product']['nama_produk']}\n\n"
        "Masukkan tanggal expired (YYYY-MM-DD):"
    )

    return INPUT_EXPIRED

# ========================
# INPUT EXPIRED
# ========================

async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expired_date = update.message.text

    try:
        datetime.strptime(expired_date, "%Y-%m-%d")
    except:
        await update.message.reply_text("❌ Format salah. Gunakan YYYY-MM-DD")
        return INPUT_EXPIRED

    user = update.effective_user
    produk = context.user_data["selected_product"]
    lokasi = context.user_data["lokasi"]

    success = save_expired(
        lokasi,
        produk["upc"],
        produk["nama_produk"],
        expired_date,
        user.full_name
    )

    if success:
        await update.message.reply_text(
            "✅ Data berhasil disimpan!\n\nKetik produk berikutnya atau tekan 🔁 Pindah Lokasi."
        )
        return CARI_PRODUK
    else:
        await update.message.reply_text("❌ Gagal menyimpan data")
        return ConversationHandler.END

# ========================
# MAIN
# ========================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PILIH_LOKASI: [
                CallbackQueryHandler(pilih_lokasi, pattern="^lokasi_")
            ],
            CARI_PRODUK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cari_produk)
            ],
            PILIH_PRODUK: [
                CallbackQueryHandler(pilih_produk)
            ],
            INPUT_EXPIRED: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_expired)
            ],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)

    print("Bot Running...")
    app.run_polling()
