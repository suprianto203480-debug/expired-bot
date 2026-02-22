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

# Ambil dari environment variable (JANGAN hardcode!)
TOKEN = os.getenv("BOT_TOKEN")  # Set BOT_TOKEN di environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Cek token tersedia
if not TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan di environment variable!")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL tidak ditemukan di environment variable!")

LOKASI, PRODUK, EXPIRED, PIC = range(4)

# ================= DATABASE =================

def get_connection():
    """Membuat koneksi database dengan error handling"""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Error koneksi database: {e}")
        return None

def create_table():
    """Membuat tabel jika belum ada"""
    conn = get_connection()
    if not conn:
        print("Gagal konek ke database untuk create table")
        return
    
    try:
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
        print("Tabel berhasil dibuat/dicek")
    except Exception as e:
        print(f"Error create table: {e}")
    finally:
        conn.close()

def save_to_db(data):
    """Menyimpan data ke database dengan error handling"""
    conn = get_connection()
    if not conn:
        print("Gagal konek ke database untuk save")
        return False
    
    try:
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
        return True
    except Exception as e:
        print(f"Error save to db: {e}")
        return False
    finally:
        conn.close()

# ================= EXCEL =================

def load_produk_master():
    """Load produk master dengan error handling"""
    try:
        if not os.path.exists("produk_master.xls"):
            print("File produk_master.xls tidak ditemukan!")
            return None
            
        df = pd.read_excel("produk_master.xls")
        df.columns = df.columns.str.strip()
        df["UPC"] = df["UPC"].astype(str).str.strip()
        return df
    except Exception as e:
        print(f"Error load produk master: {e}")
        return None

def cari_produk(upc):
    """Mencari produk berdasarkan UPC"""
    df = load_produk_master()
    if df is None or df.empty:
        return None
    
    try:
        hasil = df[df["UPC"] == str(upc).strip()]
        if not hasil.empty:
            return hasil.iloc[0]["SKU Desc"]
    except Exception as e:
        print(f"Error cari produk: {e}")
    
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
    upc = update.message.text.strip()
    nama_produk = cari_produk(upc)

    if not nama_produk:
        await update.message.reply_text(
            "❌ Produk tidak ditemukan!\n"
            "Coba scan ulang atau ketik /start untuk memulai lagi."
        )
        return PRODUK

    context.user_data["upc"] = upc
    context.user_data["nama_produk"] = nama_produk

    await update.message.reply_text(
        f"✅ Produk Ditemukan:\n"
        f"📦 {nama_produk}\n\n"
        f"📅 Input Tanggal Expired (YYYY-MM-DD):\n"
        f"Contoh: 2024-12-31"
    )
    return EXPIRED

async def expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    try:
        expired_date = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text(
            "❌ Format salah!\n"
            "Gunakan format YYYY-MM-DD\n"
            "Contoh: 2024-12-31"
        )
        return EXPIRED

    context.user_data["expired"] = expired_date

    # Keyboard PIC
    keyboard = [["Andi"], ["Budi"], ["Siti"], ["Lainnya"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text("👤 Pilih PIC:", reply_markup=reply_markup)
    return PIC

async def pic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pic"] = update.message.text
    data = context.user_data

    # Simpan ke database
    success = save_to_db(data)

    if success:
        await update.message.reply_text(
            f"✅ DATA BERHASIL TERSIMPAN\n\n"
            f"📍 Lokasi: {data['lokasi']}\n"
            f"📦 Produk: {data['nama_produk']}\n"
            f"🔢 UPC: {data['upc']}\n"
            f"📅 Expired: {data['expired']}\n"
            f"👤 PIC: {data['pic']}\n\n"
            f"Ketik /start untuk input baru"
        )
    else:
        await update.message.reply_text(
            "❌ GAGAL menyimpan ke database!\n"
            "Hubungi administrator.\n\n"
            "Ketik /start untuk coba lagi"
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Dibataalkan. Ketik /start untuk memulai lagi.")
    return ConversationHandler.END

# ================= MAIN =================

def main():
    print("Memulai bot...")
    
    # Buat tabel database
    create_table()
    
    # Cek file produk master
    if not os.path.exists("produk_master.xls"):
        print("⚠️ PERINGATAN: File produk_master.xls tidak ditemukan!")

    # Buat aplikasi bot
    app = ApplicationBuilder().token(TOKEN).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi)],
            PRODUK: [MessageHandler(filters.TEXT & ~filters.COMMAND, produk)],
            EXPIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, expired)],
            PIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, pic)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    
    print("Bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
