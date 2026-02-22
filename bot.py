import os
import csv
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

# Ambil dari environment variable
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN tidak ditemukan!")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL tidak ditemukan!")

LOKASI, PRODUK, EXPIRED, PIC = range(4)

# ================= DATABASE =================

def get_connection():
    """Membuat koneksi database"""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Error koneksi database: {e}")
        return None

def create_table():
    """Membuat tabel jika belum ada"""
    conn = get_connection()
    if not conn:
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
        print("✅ Tabel berhasil dibuat/dicek")
    except Exception as e:
        print(f"❌ Error create table: {e}")
    finally:
        conn.close()

def save_to_db(data):
    """Menyimpan data ke database"""
    conn = get_connection()
    if not conn:
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
        print(f"❌ Error save to db: {e}")
        return False
    finally:
        conn.close()

# ================= CSV PRODUK =================

def load_produk_master():
    """Load produk dari CSV"""
    produk_dict = {}
    try:
        # Cek file existence
        if not os.path.exists("produk_master.csv"):
            print("❌ File produk_master.csv TIDAK DITEMUKAN!")
            print(f"📁 Current directory: {os.getcwd()}")
            print(f"📂 SEMUA FILE: {os.listdir('.')}")
            return {}
        
        print("✅ File produk_master.csv DITEMUKAN")
        with open('produk_master.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            # Cek header
            if not reader.fieldnames:
                print("❌ Header CSV tidak ditemukan!")
                return {}
            
            print(f"📋 Header CSV: {reader.fieldnames}")
            
            row_count = 0
            for row in reader:
                upc = row['UPC'].strip()
                nama = row['SKU Desc'].strip()
                produk_dict[upc] = nama
                row_count += 1
                if row_count <= 3:
                    print(f"  ✅ Contoh {row_count}: UPC='{upc}' -> '{nama}'")
        
        print(f"📊 TOTAL: {len(produk_dict)} produk berhasil di-load")
        return produk_dict
        
    except Exception as e:
        print(f"❌ ERROR DETAIL: {type(e).__name__}: {e}")
        return {}

def cari_produk(upc):
    """Mencari produk berdasarkan UPC"""
    upc_str = str(upc).strip()
    print(f"🔍 MENCARI UPC: '{upc_str}'")
    
    produk_dict = load_produk_master()
    
    if not produk_dict:
        print("❌ Database produk kosong!")
        return None
    
    if upc_str in produk_dict:
        print(f"✅ Ditemukan: {produk_dict[upc_str]}")
        return produk_dict[upc_str]
    else:
        print(f"❌ UPC '{upc_str}' tidak ditemukan")
        print(f"📋 Sample UPC di DB: {list(produk_dict.keys())[:5]}")
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
    keyboard = [["Andi"], ["Budi"], ["Siti"]]
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
    await update.message.reply_text("❌ Dibatalkan. Ketik /start untuk memulai lagi.")
    return ConversationHandler.END

# ================= MAIN =================

def main():
    print("🚀 Memulai bot...")
    
    # Buat tabel database
    create_table()
    
    # Test load produk
    print("📊 Test load produk master...")
    produk = load_produk_master()
    if produk:
        print(f"✅ Siap! {len(produk)} produk tersedia")
    else:
        print("⚠️ PERINGATAN: Tidak ada produk!")

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
    
    print("✅ Bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
