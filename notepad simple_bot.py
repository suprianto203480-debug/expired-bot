"""
File: simple_bot.py
Bot Telegram dengan error handling yang baik
"""

import os
import logging
import time
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import psycopg2

# ============= KONFIGURASI =============
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 8080))
# =======================================

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

print("="*50)
print("🚀 SIMPLE BOT STARTING...")
print(f"📅 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"🤖 TOKEN: {'✅ SET' if TOKEN else '❌ NOT SET'}")
print(f"🗄️  DATABASE_URL: {'✅ SET' if DATABASE_URL else '❌ NOT SET'}")
print("="*50)

def get_db_connection():
    """Membuat koneksi ke database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return None

# Test koneksi database
try:
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"✅ Database terhubung! Total {total} produk")
    else:
        total = 0
        print("❌ Gagal konek database")
except Exception as e:
    print(f"❌ Error: {e}")
    total = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start"""
    try:
        user = update.effective_user
        logger.info(f"📩 /start dari {user.first_name} (ID: {user.id})")
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Cari Produk", callback_data='cari'),
                InlineKeyboardButton("📦 List Dept", callback_data='list_dept')
            ],
            [InlineKeyboardButton("ℹ️ Info", callback_data='info')]
        ]
        
        await update.message.reply_text(
            f"👋 *Halo {user.first_name}!*\n\n"
            f"🤖 *RAS BOT - Scanner Produk*\n"
            f"📊 Database: {total} produk\n"
            f"─────────────────────\n"
            f"Silahkan pilih menu:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"❌ Error in start: {e}")
        await update.message.reply_text("⚠️ Terjadi error, coba lagi nanti")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk tombol"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'cari':
        await query.edit_message_text(
            "🔍 Masukkan kata kunci (nama produk atau SKU):",
            parse_mode='Markdown'
        )
        context.user_data['state'] = 'WAITING_SEARCH'
    
    elif query.data == 'list_dept':
        keyboard = [
            [InlineKeyboardButton("🏢 Dept 61", callback_data='dept_61_0')],
            [InlineKeyboardButton("🏢 Dept 69", callback_data='dept_69_0')],
            [InlineKeyboardButton("🏢 Dept 97", callback_data='dept_97_0')],
            [InlineKeyboardButton("◀️ Kembali", callback_data='menu')]
        ]
        await query.edit_message_text(
            "📦 *PILIH DEPARTMENT*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith('dept_'):
        parts = query.data.split('_')
        dept = parts[1]
        page = int(parts[2])
        
        conn = get_db_connection()
        if not conn:
            await query.edit_message_text("❌ Gagal konek database")
            return
        
        cursor = conn.cursor()
        
        items_per_page = 5
        offset = page * items_per_page
        
        cursor.execute(
            "SELECT sku, nama_produk FROM products WHERE dept = %s ORDER BY sku LIMIT %s OFFSET %s",
            (dept, items_per_page, offset)
        )
        items = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE dept = %s", (dept,))
        total_items = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        total_pages = (total_items - 1) // items_per_page + 1
        
        keyboard = []
        for sku, nama in items:
            short_nama = nama[:30] + '...' if len(nama) > 30 else nama
            keyboard.append([
                InlineKeyboardButton(f"📦 {short_nama}", callback_data=f'detail_{sku}')
            ])
        
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f'dept_{dept}_{page-1}'))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data=f'dept_{dept}_{page+1}'))
        if nav:
            keyboard.append(nav)
        
        keyboard.append([InlineKeyboardButton("◀️ Kembali", callback_data='list_dept')])
        
        await query.edit_message_text(
            f"📁 *Department {dept}*\n"
            f"Halaman {page+1}/{total_pages} | Total {total_items} produk",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith('detail_'):
        sku = query.data.replace('detail_', '')
        conn = get_db_connection()
        if not conn:
            await query.edit_message_text("❌ Gagal konek database")
            return
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE sku = %s", (sku,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if product:
            dept, sku, nama, upc = product
            await query.edit_message_text(
                f"📦 *DETAIL PRODUK*\n\n"
                f"🏷️ SKU: `{sku}`\n"
                f"📝 Nama: {nama}\n"
                f"🔢 UPC: `{upc}`\n"
                f"🏢 Dept: {dept}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Kembali", callback_data=f'dept_{dept}_0')
                ]])
            )
    
    elif query.data == 'info':
        await query.edit_message_text(
            "ℹ️ *INFORMASI BOT*\n\n"
            f"📊 *Total Database:* {total} produk\n\n"
            "📌 *Cara Penggunaan:*\n"
            "• 🔍 *Cari:* Ketik nama/SKU/UPC\n"
            "• 📦 *List Dept:* Lihat per department\n\n"
            "Dibuat oleh: @suprianto203480",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Kembali", callback_data='menu')
            ]])
        )
    
    elif query.data == 'menu':
        await start(query, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk pesan teks"""
    text = update.message.text.strip()
    state = context.user_data.get('state')
    
    conn = get_db_connection()
    if not conn:
        await update.message.reply_text("❌ Gagal konek database")
        return
    
    cursor = conn.cursor()
    
    if state == 'WAITING_SEARCH':
        # Cari berdasarkan keyword
        cursor.execute(
            "SELECT dept, sku, nama_produk FROM products WHERE "
            "nama_produk ILIKE %s OR sku ILIKE %s OR upc ILIKE %s "
            "LIMIT 10",
            (f'%{text}%', f'%{text}%', f'%{text}%')
        )
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if results:
            msg = f"🔍 *Hasil pencarian:* `{text}`\n\n"
            for dept, sku, nama in results:
                msg += f"• *{nama[:50]}...*\n  SKU: `{sku}` (Dept {dept})\n\n"
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Tidak ditemukan: `{text}`", parse_mode='Markdown')
        context.user_data['state'] = None
    
    else:
        # Cek sebagai barcode dulu
        cursor.execute("SELECT * FROM products WHERE upc = %s", (text,))
        result = cursor.fetchone()
        
        if result:
            dept, sku, nama, upc = result
            cursor.close()
            conn.close()
            await update.message.reply_text(
                f"✅ *DITEMUKAN!*\nSKU: {sku}\n{nama}",
                parse_mode='Markdown'
            )
        else:
            # Cek sebagai SKU
            cursor.execute("SELECT * FROM products WHERE sku = %s", (text,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                dept, sku, nama, upc = result
                await update.message.reply_text(
                    f"✅ *DITEMUKAN (via SKU)!*\nSKU: {sku}\n{nama}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Tidak ditemukan. Gunakan /start")

def main():
    """Main function"""
    try:
        print("🤖 Memulai bot...")
        
        # Buat aplikasi
        app = Application.builder().token(TOKEN).build()
        
        # Tambah handler
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        print("✅ Bot siap! Menjalankan polling...")
        print("="*50)
        
        # Jalankan bot
        app.run_polling()
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"❌ Bot crash: {e}")
        time.sleep(5)
        sys.exit(1)

if __name__ == "__main__":
    main()
