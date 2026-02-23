import os
import psycopg2
import logging
from flask import Flask, request, jsonify, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import threading

# ============= KONFIGURASI =============
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 5000))
# =======================================

# Setup Flask untuk WebApp
app_flask = Flask(__name__, static_folder='static', template_folder='templates')

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Membuat koneksi ke PostgreSQL Railway"""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Test koneksi database
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    print(f"✅ Database terhubung! Total {total} produk")
    conn.close()
except Exception as e:
    print(f"❌ Gagal konek database: {e}")
    total = 0

# ============= ROUTES FLASK UNTUK WEBAPP =============
@app_flask.route('/')
def index():
    """Halaman utama webapp"""
    return send_from_directory('templates', 'scanner.html')

@app_flask.route('/api/search', methods=['POST'])
def search_product():
    """API untuk mencari produk berdasarkan barcode"""
    try:
        data = request.json
        barcode = data.get('barcode', '').strip()
        
        if not barcode:
            return jsonify({'found': False, 'error': 'Barcode tidak valid'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Cari di database
        cursor.execute(
            "SELECT dept, sku, nama_produk, upc FROM products WHERE upc = %s",
            (barcode,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                'found': True,
                'product': {
                    'dept': result[0],
                    'sku': result[1],
                    'nama_produk': result[2],
                    'upc': result[3]
                }
            })
        else:
            return jsonify({'found': False})
            
    except Exception as e:
        logger.error(f"Error in search API: {e}")
        return jsonify({'found': False, 'error': str(e)}), 500

# ============= HANDLER BOT TELEGRAM =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk perintah /start dengan WebApp"""
    user = update.effective_user
    
    # Base URL untuk webapp (ganti dengan URL Railway Anda)
    BASE_URL = "BASE_URL = "https://expired-bot-production.up.railway.app"  # GANTI DENGAN URL RAILWAY ANDA
    
    # Buat keyboard dengan tombol WebApp
    keyboard = [
        [KeyboardButton(
            text="📷 Scan Barcode (Kamera)",
            web_app=WebAppInfo(url=f"{BASE_URL}")
        )],
        [
            InlineKeyboardButton("🔍 Cari Manual", callback_data='cari'),
            InlineKeyboardButton("📦 List Dept", callback_data='list_dept')
        ],
        [InlineKeyboardButton("ℹ️ Info", callback_data='info')]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"👋 *Halo {user.first_name}!*\n\n"
        f"🤖 *RAS BOT - Scanner Produk*\n"
        f"📊 Database: {total} produk\n"
        f"─────────────────────\n"
        f"✨ *Fitur Baru:* Scan dengan Kamera!\n"
        f"Klik tombol di bawah untuk mulai:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk tombol inline"""
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
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE sku = %s", (sku,))
        product = cursor.fetchone()
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
            "• 📷 *Scan Kamera:* Klik tombol di keyboard\n"
            "• 🔍 *Cari Manual:* Ketik nama/SKU\n"
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
        
        if results:
            msg = f"🔍 *Hasil pencarian:* `{text}`\n\n"
            for dept, sku, nama in results:
                msg += f"• *{nama[:50]}...*\n  SKU: `{sku}` (Dept {dept})\n\n"
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Tidak ditemukan: `{text}`", parse_mode='Markdown')
        context.user_data['state'] = None
    
    else:
        # Cek sebagai barcode
        cursor.execute("SELECT * FROM products WHERE upc = %s", (text,))
        result = cursor.fetchone()
        
        if result:
            dept, sku, nama, upc = result
            await update.message.reply_text(
                f"✅ *DITEMUKAN!*\nSKU: {sku}\n{nama}",
                parse_mode='Markdown'
            )
        else:
            # Cek sebagai SKU
            cursor.execute("SELECT * FROM products WHERE sku = %s", (text,))
            result = cursor.fetchone()
            
            if result:
                dept, sku, nama, upc = result
                await update.message.reply_text(
                    f"✅ *DITEMUKAN (via SKU)!*\nSKU: {sku}\n{nama}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Tidak ditemukan. Gunakan /start")
    
    conn.close()

def run_bot():
    """Menjalankan bot Telegram"""
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Bot Telegram berjalan...")
    app.run_polling()

def run_flask():
    """Menjalankan Flask server"""
    print(f"🌐 WebApp berjalan di port {PORT}")
    app_flask.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    # Jalankan Flask di thread terpisah
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Jalankan bot di thread utama
    run_bot()

