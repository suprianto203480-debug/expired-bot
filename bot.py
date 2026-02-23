import os
import psycopg2
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============= KONFIGURASI =============
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
# =======================================

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk perintah /start"""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📷 Scan Barcode", callback_data='scan')],
        [InlineKeyboardButton("🔍 Cari Produk", callback_data='cari')],
        [InlineKeyboardButton("📦 List by Dept", callback_data='list_dept')],
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk tombol inline"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'scan':
        keyboard = [
            [InlineKeyboardButton("⌨️ Ketik Barcode", callback_data='ketik')],
            [InlineKeyboardButton("◀️ Kembali", callback_data='menu')]
        ]
        await query.edit_message_text(
            "📷 *SCAN BARCODE*\n\n"
            "Silahkan **ketik** angka barcode:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['state'] = 'WAITING_BARCODE'
    
    elif query.data == 'ketik':
        await query.edit_message_text(
            "⌨️ Masukkan angka barcode/UPC:",
            parse_mode='Markdown'
        )
        context.user_data['state'] = 'WAITING_BARCODE'
    
    elif query.data == 'cari':
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
            keyboard = [
                [InlineKeyboardButton("🔍 Cari UPC Ini", callback_data=f'cari_upc_{upc}')],
                [InlineKeyboardButton("◀️ Kembali ke Dept", callback_data=f'dept_{dept}_0')],
                [InlineKeyboardButton("◀️◀️ Menu Utama", callback_data='menu')]
            ]
            await query.edit_message_text(
                f"📦 *DETAIL PRODUK*\n\n"
                f"🏷️ *SKU:* `{sku}`\n"
                f"📝 *Nama:* {nama}\n"
                f"🔢 *UPC:* `{upc}`\n"
                f"🏢 *Dept:* {dept}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif query.data.startswith('cari_upc_'):
        upc = query.data.replace('cari_upc_', '')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE upc = %s", (upc,))
        product = cursor.fetchone()
        conn.close()
        
        if product:
            dept, sku, nama, upc = product
            await query.edit_message_text(
                f"✅ *PRODUK DITEMUKAN (via UPC)*\n\n"
                f"🏷️ SKU: `{sku}`\n"
                f"📝 Nama: {nama}\n"
                f"🔢 UPC: `{upc}`\n"
                f"🏢 Dept: {dept}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Kembali", callback_data=f'detail_{sku}')
                ]])
            )
    
    elif query.data == 'info':
        await query.edit_message_text(
            "ℹ️ *INFORMASI BOT*\n\n"
            f"📊 *Total Database:* {total} produk\n"
            "📌 *Department:*\n"
            "   • Dept 61: 1.745 produk\n"
            "   • Dept 69: 1.461 produk\n"
            "   • Dept 97: 1.048 produk\n\n"
            "📌 *Cara Penggunaan:*\n"
            "• *Scan Barcode:* Ketik angka UPC\n"
            "• *Cari Produk:* Ketik nama/SKU\n"
            "• *List Dept:* Lihat produk per department\n\n"
            "📌 *Contoh:*\n"
            "• UPC: `8993200668243`\n"
            "• SKU: `97418914`\n"
            "• Nama: `SOSIS`\n\n"
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
    
    print(f"📩 Input: {text}, State: {state}")  # Log untuk debugging
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ===== STATE: WAITING_BARCODE (dari menu scan) =====
    if state == 'WAITING_BARCODE':
        # Cari berdasarkan UPC (barcode)
        cursor.execute("SELECT * FROM products WHERE upc = %s", (text,))
        result = cursor.fetchone()
        
        if result:
            dept, sku, nama, upc = result
            keyboard = [
                [InlineKeyboardButton("📦 Lihat Detail", callback_data=f'detail_{sku}')],
                [InlineKeyboardButton("🔍 Scan Lagi", callback_data='scan')]
            ]
            await update.message.reply_text(
                f"✅ *PRODUK DITEMUKAN!*\n\n"
                f"🏷️ SKU: `{sku}`\n"
                f"📦 Nama: {nama}\n"
                f"🏢 Dept: {dept}\n"
                f"🔢 UPC: `{upc}`",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Coba cari sebagai SKU
            cursor.execute("SELECT * FROM products WHERE sku = %s", (text,))
            result = cursor.fetchone()
            
            if result:
                dept, sku, nama, upc = result
                keyboard = [
                    [InlineKeyboardButton("📦 Lihat Detail", callback_data=f'detail_{sku}')],
                    [InlineKeyboardButton("🔍 Scan Lagi", callback_data='scan')]
                ]
                await update.message.reply_text(
                    f"✅ *PRODUK DITEMUKAN (via SKU)!*\n\n"
                    f"🏷️ SKU: `{sku}`\n"
                    f"📦 Nama: {nama}\n"
                    f"🏢 Dept: {dept}\n"
                    f"🔢 UPC: `{upc}`",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard = [[InlineKeyboardButton("🔍 Coba Lagi", callback_data='scan')]]
                await update.message.reply_text(
                    f"❌ Barcode/SKU `{text}` tidak ditemukan.",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        context.user_data['state'] = None
    
    # ===== STATE: WAITING_SEARCH (dari menu cari) =====
    elif state == 'WAITING_SEARCH':
        # Cari berdasarkan keyword di nama produk atau SKU
        cursor.execute(
            "SELECT dept, sku, nama_produk FROM products WHERE "
            "nama_produk ILIKE %s OR sku ILIKE %s OR upc ILIKE %s "
            "LIMIT 10",
            (f'%{text}%', f'%{text}%', f'%{text}%')
        )
        results = cursor.fetchall()
        
        if results:
            msg = f"🔍 *Hasil pencarian:* `{text}`\n\n"
            keyboard = []
            
            for dept, sku, nama in results:
                short_nama = nama[:40] + '...' if len(nama) > 40 else nama
                msg += f"• *{short_nama}*\n  SKU: `{sku}` (Dept {dept})\n\n"
                keyboard.append([InlineKeyboardButton(f"📦 {short_nama}", callback_data=f'detail_{sku}')])
            
            keyboard.append([InlineKeyboardButton("🔍 Cari Lagi", callback_data='cari')])
            
            await update.message.reply_text(
                msg,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton("🔍 Coba Lagi", callback_data='cari')]]
            await update.message.reply_text(
                f"❌ Tidak ditemukan produk dengan kata kunci: `{text}`",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        context.user_data['state'] = None
    
    # ===== TANPA STATE (input langsung) =====
    else:
        # Cek sebagai UPC dulu
        cursor.execute("SELECT * FROM products WHERE upc = %s", (text,))
        result = cursor.fetchone()
        
        if result:
            dept, sku, nama, upc = result
            keyboard = [[InlineKeyboardButton("📦 Lihat Detail", callback_data=f'detail_{sku}')]]
            await update.message.reply_text(
                f"✅ *PRODUK DITEMUKAN!*\n\n"
                f"🏷️ SKU: `{sku}`\n"
                f"📦 Nama: {nama}\n"
                f"🏢 Dept: {dept}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Cek sebagai SKU
            cursor.execute("SELECT * FROM products WHERE sku = %s", (text,))
            result = cursor.fetchone()
            
            if result:
                dept, sku, nama, upc = result
                keyboard = [[InlineKeyboardButton("📦 Lihat Detail", callback_data=f'detail_{sku}')]]
                await update.message.reply_text(
                    f"✅ *PRODUK DITEMUKAN (via SKU)!*\n\n"
                    f"🏷️ SKU: `{sku}`\n"
                    f"📦 Nama: {nama}\n"
                    f"🏢 Dept: {dept}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # Cek sebagai nama produk (partial match)
                cursor.execute(
                    "SELECT dept, sku, nama_produk FROM products WHERE nama_produk ILIKE %s LIMIT 10",
                    (f'%{text}%',)
                )
                results = cursor.fetchall()
                
                if results:
                    msg = f"🔍 *Hasil pencarian untuk:* `{text}`\n\n"
                    keyboard = []
                    
                    for dept, sku, nama in results:
                        short_nama = nama[:40] + '...' if len(nama) > 40 else nama
                        msg += f"• *{short_nama}*\n  SKU: `{sku}` (Dept {dept})\n\n"
                        keyboard.append([InlineKeyboardButton(f"📦 {short_nama}", callback_data=f'detail_{sku}')])
                    
                    keyboard.append([InlineKeyboardButton("🔍 Cari Lagi", callback_data='cari')])
                    
                    await update.message.reply_text(
                        msg,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await update.message.reply_text(
                        f"❌ Tidak ditemukan produk dengan UPC/SKU/Nama: `{text}`\n\n"
                        f"Gunakan /start untuk menu utama.",
                        parse_mode='Markdown'
                    )
    
    conn.close()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk error"""
    logger.warning(f"Update {update} caused error {context.error}")

def main():
    """Main function"""
    # Buat aplikasi
    app = Application.builder().token(TOKEN).build()
    
    # Handler commands
    app.add_handler(CommandHandler("start", start))
    
    # Handler untuk tombol
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Handler untuk teks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Handler error
    app.add_error_handler(error_handler)
    
    print("🤖 Bot berjalan... Tekan Ctrl+C untuk stop")
    print(f"📊 Database: {total} produk siap digunakan")
    app.run_polling()

if __name__ == '__main__':
    main()
