import os
import pandas as pd
import psycopg2
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw")
DATABASE_URL = os.getenv("DATABASE_URL")

LOKASI, PRODUK, EXPIRED, PIC = range(4)

# ================= DATABASE =================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def create_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expired_logs (
            id SERIAL PRIMARY KEY,
            tanggal_input TIMESTAMP,
            lokasi TEXT,
            upc TEXT,
            nama_produk TEXT,
            expired_date DATE,
            pic TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_to_db(data):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expired_logs
        (tanggal_input, lokasi, upc, nama_produk, expired_date, pic)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        datetime.now(),
        data["lokasi"],
        data["upc"],
        data["nama_produk"],
        data["expired"],
        data["pic"],
    ))
    conn.commit()
    cur.close()
    conn.close()

# ================= EXCEL =================

def load_produk_master():
    df = pd.read_excel("produk_master.xls")
    df.columns = df.columns.str.strip()
    df["UPC"] = df["UPC"].astype(str).str.strip()
    return df

def cari_produk(upc):
    df = load_produk_master()
    hasil = df[df["UPC"] == str(upc)]
    if not hasil.empty:
        return hasil.iloc[0]["SKU Desc"]
    return None

# ================= BOT FLOW =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Scan / Input Lokasi:")
    return LOKASI

async def lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lokasi"] = update.message.text
    await update.message.reply_text("📦 Scan Barcode Produk:")
    return PRODUK

async def produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upc = update.message.text
    nama_produk = cari_produk(upc)

    if not nama_produk:
        await update.message.reply_text("❌ Produk tidak ditemukan!")
        return PRODUK

    context.user_data["upc"] = upc
    context.user_data["nama_produk"] = nama_produk

    await update.message.reply_text(
        f"✅ Produk:\n📦 {nama_produk}\n\n📅 Input Expired (YYYY-MM-DD):"
    )
    return EXPIRED

async def expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        expired_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
    except:
        await update.message.reply_text("❌ Format salah! Gunakan YYYY-MM-DD")
        return EXPIRED

    context.user_data["expired"] = expired_date

    keyboard = [["Andi"], ["Budi"], ["Siti"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text("👤 Pilih PIC:", reply_markup=reply_markup)
    return PIC

async def pic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pic"] = update.message.text
    data = context.user_data

    save_to_db(data)

    await update.message.reply_text(
        f"✅ DATA TERSIMPAN\n\n"
        f"📍 {data['lokasi']}\n"
        f"📦 {data['nama_produk']}\n"
        f"🔢 {data['upc']}\n"
        f"📅 {data['expired']}\n"
        f"👤 {data['pic']}"
    )

    return ConversationHandler.END

# ================= MAIN =================

def main():
    create_table()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi)],
            PRODUK: [MessageHandler(filters.TEXT & ~filters.COMMAND, produk)],
            EXPIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, expired)],
            PIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, pic)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
