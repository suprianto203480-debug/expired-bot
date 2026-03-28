import os
import logging
import psycopg2
import csv
import pytz
import asyncio
import threading
from datetime import datetime, date

from flask import Flask, request

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

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_IDS = [5285453784]

PILIH_LOKASI, CARI_PRODUK, PILIH_PRODUK, INPUT_EXPIRED, TAMBAH_LAGI = range(5)

# ================= DATABASE =================

import time

def get_connection(retries=5, delay=2):
    for i in range(retries):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except Exception as e:
            print(f"Retry DB ke-{i+1} gagal: {e}")
            time.sleep(delay)
    raise Exception("Database tidak bisa dihubungi")

def user_exists(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nama FROM users WHERE telegram_id=%s AND is_active=true", (telegram_id,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    return data

def get_user_by_telegram_id(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username,nama,role,is_active FROM users WHERE telegram_id=%s", (telegram_id,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    return data

def get_locations():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id,nama_lokasi FROM locations WHERE is_active=true")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data

def search_product(keyword):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT upc, sku, deskripsi
        FROM products
        WHERE upc ILIKE %s OR sku::text ILIKE %s OR deskripsi ILIKE %s
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
        INSERT INTO expired_logs (tanggal_input,lokasi,upc,nama_produk,expired_date,pic)
        VALUES ((NOW() AT TIME ZONE 'Asia/Jakarta'),%s,%s,%s,%s,%s)
    """, (lokasi_id, upc, nama_produk, expired_date, pic))
    conn.commit()
    cur.close()
    conn.close()

# ================= MENU =================

def main_menu():
    return ReplyKeyboardMarkup([
        ["➕ Input Produk", "📄 Export Harian"],
        ["📊 Rekap Bulanan CSV", "🗑 Hapus Item"],
        ["🚨 Notifikasi Expired"],
        ["ℹ️ Help"],
        ["🏠 Menu Utama"]
    ], resize_keyboard=True)

# ================= HANDLER =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_exists(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Anda tidak terdaftar.")
        return
    await update.message.reply_text(f"Halo {user[0]}", reply_markup=main_menu())

async def start_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    locations = get_locations()
    keyboard = [[InlineKeyboardButton(l[1], callback_data=f"lokasi_{l[0]}")] for l in locations]
    await update.message.reply_text("Pilih Lokasi:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_LOKASI

async def pilih_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lokasi_id = query.data.split("_")[1]
    context.user_data["lokasi"] = lokasi_id

    user = get_user_by_telegram_id(update.effective_user.id)
    context.user_data["pic"] = user[1]

    await query.edit_message_text("Ketik SKU / Nama / UPC:")
    return CARI_PRODUK

async def cari_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = search_product(update.message.text)
    if not results:
        await update.message.reply_text("Tidak ditemukan")
        return CARI_PRODUK

    keyboard = [[InlineKeyboardButton(p["nama_produk"], callback_data=f"produk_{p['upc']}")] for p in results]
    context.user_data["last"] = results
    await update.message.reply_text("Pilih:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_PRODUK

async def pilih_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    upc = query.data.split("_")[1]
    produk = next(p for p in context.user_data["last"] if p["upc"] == upc)

    context.user_data["produk"] = produk

    await query.edit_message_text("Masukkan expired (ddmmyy):")
    return INPUT_EXPIRED

async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        expired = datetime.strptime(update.message.text, "%d%m%y").date()
    except:
        await update.message.reply_text("Format salah")
        return INPUT_EXPIRED

    p = context.user_data["produk"]

    save_expired(
        context.user_data["lokasi"],
        p["upc"],
        p["nama_produk"],
        expired,
        context.user_data["pic"]
    )

    await update.message.reply_text("✅ Tersimpan", reply_markup=main_menu())
    return ConversationHandler.END

# ================= EXPORT =================

async def export_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Export belum diaktifkan di versi ini")

async def export_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Export bulanan belum aktif")

# ================= NOTIF =================

async def notifikasi_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚨 Belum ada data")

# ================= FLASK =================

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot Running"

@flask_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, telegram_app.bot)

        telegram_app.update_queue.put_nowait(update)

        return "ok"
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "error"
# ================= MAIN =================

if __name__ == "__main__":

    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    PORT = int(os.getenv("PORT", 8080))

    telegram_app = ApplicationBuilder().token(TOKEN).build()

    asyncio.run(telegram_app.initialize())
    asyncio.run(telegram_app.start())

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("➕ Input Produk"), start_input)],
        states={
            PILIH_LOKASI: [CallbackQueryHandler(pilih_lokasi)],
            CARI_PRODUK: [MessageHandler(filters.TEXT, cari_produk)],
            PILIH_PRODUK: [CallbackQueryHandler(pilih_produk)],
            INPUT_EXPIRED: [MessageHandler(filters.TEXT, input_expired)],
        },
        fallbacks=[],
        per_message=True,
    )

    telegram_app.add_handler(conv)
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.Text("📄 Export Harian"), export_harian))
    telegram_app.add_handler(MessageHandler(filters.Text("📊 Rekap Bulanan CSV"), export_bulanan))
    telegram_app.add_handler(MessageHandler(filters.Text("🚨 Notifikasi Expired"), notifikasi_expired))

    asyncio.run(telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook"))

    print("✅ BOT LIVE")

    def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_flask).start()
