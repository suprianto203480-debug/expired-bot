import os
import sqlite3
import csv
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters,
    ContextTypes, ConversationHandler
)

TOKEN = os.getenv("TOKEN")

DB_NAME = "expired.db"

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS master_produk (
        sku TEXT PRIMARY KEY,
        nama_produk TEXT,
        upc TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS expired_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lokasi TEXT,
        sku TEXT,
        nama_produk TEXT,
        upc TEXT,
        expired_date DATE,
        pic TEXT,
        input_date DATE
    )
    """)

    conn.commit()
    conn.close()


def get_produk(sku):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT nama_produk, upc FROM master_produk WHERE sku=?", (sku,))
    data = c.fetchone()
    conn.close()
    return data


def insert_expired(data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    INSERT INTO expired_data
    (lokasi, sku, nama_produk, upc, expired_date, pic, input_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()
    conn.close()


def get_today_expired():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = date.today()
    c.execute("SELECT * FROM expired_data WHERE input_date=?", (today,))
    data = c.fetchall()
    conn.close()
    return data


def get_monthly_report(year, month):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    SELECT lokasi, sku, nama_produk, upc, expired_date, pic, input_date
    FROM expired_data
    WHERE strftime('%Y', input_date)=?
    AND strftime('%m', input_date)=?
    """, (str(year), f"{month:02d}"))
    data = c.fetchall()
    conn.close()
    return data


def delete_data(id_data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM expired_data WHERE id=?", (id_data,))
    conn.commit()
    conn.close()


# ================= MENU =================

main_menu = ReplyKeyboardMarkup([
    ["➕ Input Expired"],
    ["📄 Export Harian", "📊 Export Bulanan"],
    ["🗑 Hapus Data"]
], resize_keyboard=True)


# ================= CONVERSATION =================

LOKASI, SKU, EXPIRED, PIC = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Monitoring Expired Aktif 🚀", reply_markup=main_menu)


async def input_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Masukkan Lokasi:")
    return LOKASI


async def input_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lokasi"] = update.message.text
    await update.message.reply_text("Masukkan SKU:")
    return SKU


async def input_sku(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sku = update.message.text
    produk = get_produk(sku)

    if not produk:
        await update.message.reply_text("SKU tidak ditemukan di master.")
        return ConversationHandler.END

    context.user_data["sku"] = sku
    context.user_data["nama_produk"] = produk[0]
    context.user_data["upc"] = produk[1]

    await update.message.reply_text(
        f"Produk: {produk[0]}\nUPC: {produk[1]}\n\nMasukkan Tanggal Expired (YYYY-MM-DD):"
    )
    return EXPIRED


async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["expired"] = update.message.text
    await update.message.reply_text("Masukkan Nama PIC:")
    return PIC


async def input_pic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = (
        context.user_data["lokasi"],
        context.user_data["sku"],
        context.user_data["nama_produk"],
        context.user_data["upc"],
        context.user_data["expired"],
        update.message.text,
        date.today()
    )

    insert_expired(data)

    await update.message.reply_text("Data berhasil disimpan ✅", reply_markup=main_menu)
    return ConversationHandler.END


# ================= EXPORT =================

async def export_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_today_expired()

    if not data:
        await update.message.reply_text("Tidak ada data hari ini.")
        return

    filename = "export_harian.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID","Lokasi","SKU","Produk","UPC","Expired","PIC","Input Date"])
        writer.writerows(data)

    with open(filename, "rb") as f:
        await update.message.reply_document(f)

    os.remove(filename)


async def export_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    data = get_monthly_report(now.year, now.month)

    if not data:
        await update.message.reply_text("Tidak ada data bulan ini.")
        return

    filename = "export_bulanan.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Lokasi","SKU","Produk","UPC","Expired","PIC","Input Date"])
        writer.writerows(data)

    with open(filename, "rb") as f:
        await update.message.reply_document(f)

    os.remove(filename)


# ================= DELETE =================

async def hapus_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Masukkan ID data yang ingin dihapus:")
    return 100


async def proses_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_data(update.message.text)
    await update.message.reply_text("Data berhasil dihapus ✅", reply_markup=main_menu)
    return ConversationHandler.END


# ================= MAIN =================

def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Input Expired$"), input_start)],
        states={
            LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_lokasi)],
            SKU: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_sku)],
            EXPIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_expired)],
            PIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_pic)],
        },
        fallbacks=[]
    )

    hapus_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑 Hapus Data$"), hapus_data)],
        states={
            100: [MessageHandler(filters.TEXT & ~filters.COMMAND, proses_hapus)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(hapus_handler)
    app.add_handler(MessageHandler(filters.Regex("^📄 Export Harian$"), export_harian))
    app.add_handler(MessageHandler(filters.Regex("^📊 Export Bulanan$"), export_bulanan))

    app.run_polling()


if __name__ == "__main__":
    main()
