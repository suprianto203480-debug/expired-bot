import os
import json
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler,
    JobQueue
)
from telegram.constants import ParseMode
import asyncio

# ===================== KONFIGURASI =====================
TOKEN = "8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw"
DATA_FILE = "produk_database.json"

# States untuk ConversationHandler
NAMA, TANGGAL, TIPE_LOKASI, PLUGIN, SHOWCASE, KATEGORI = range(6)

# Flask app untuk webhook
app = Flask(__name__)

# Bot application
bot_app = None

# ===================== DATABASE JSON =====================
def load_data():
    """Load data dari file JSON"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    """Save data ke file JSON"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user_data(user_id):
    """Get data spesifik user"""
    data = load_data()
    return data.get(str(user_id), {"produk": [], "notifikasi": {}})

def save_user_data(user_id, user_data):
    """Save data spesifik user"""
    data = load_data()
    data[str(user_id)] = user_data
    save_data(data)

# ===================== NOTIFIKASI OTOMATIS =====================
async def cek_expired(context: ContextTypes.DEFAULT_TYPE):
    """Cek produk expired dan kirim notifikasi otomatis"""
    print(f"🔔 Cek expired: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    data = load_data()
    today = datetime.now().date()
    
    for user_id_str, user_data in data.items():
        produk_list = user_data.get("produk", [])
        notifikasi_terkirim = user_data.get("notifikasi", {})
        notifikasi_baru = {}
        
        for produk in produk_list:
            try:
                expired_date = datetime.strptime(produk['tanggal'], '%Y-%m-%d').date()
                selisih = (expired_date - today).days
                produk_id = f"{produk['nama']}_{produk['tanggal']}"
                
                # NOTIFIKASI H-7
                if selisih == 7 and notifikasi_terkirim.get(produk_id) != 7:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-7!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⏰ *Tersisa 7 hari lagi!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 7
                
                # NOTIFIKASI H-3
                elif selisih == 3 and notifikasi_terkirim.get(produk_id) != 3:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-3!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⏰ *Tersisa 3 hari lagi!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 3
                
                # NOTIFIKASI H-1
                elif selisih == 1 and notifikasi_terkirim.get(produk_id) != 1:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-1!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⏰ *BESOK EXPIRED!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 1
                
                # NOTIFIKASI EXPIRED HARI INI
                elif selisih == 0 and notifikasi_terkirim.get(produk_id) != "expired_hari_ini":
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"❌ *EXPIRED HARI INI!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⚠️ *Produk sudah expired hari ini!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = "expired_hari_ini"
                
                # NOTIFIKASI SUDAH EXPIRED
                elif selisih < 0 and notifikasi_terkirim.get(produk_id) != "expired":
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"❌ *PRODUK SUDAH EXPIRED!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⚠️ *Sudah {abs(selisih)} hari expired!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = "expired"
                
                else:
                    if produk_id in notifikasi_terkirim:
                        notifikasi_baru[produk_id] = notifikasi_terkirim[produk_id]
                        
            except Exception as e:
                print(f"Error notifikasi: {e}")
        
        # Update status notifikasi
        user_data["notifikasi"] = notifikasi_baru
        save_user_data(user_id_str, user_data)

# ===================== HANDLER BOT =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu utama"""
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="tambah")],
        [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="list")],
        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="hapus")],
        [InlineKeyboardButton("📊 STATISTIK", callback_data="stats")],
        [InlineKeyboardButton("📍 CEK LOKASI", callback_data="lokasi")],
        [InlineKeyboardButton("❓ BANTUAN", callback_data="bantuan")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏪 *MONITORING EXPIRED PRO* 🏪\n\n"
        "Sistem manajemen expired dengan *lokasi bertingkat*:\n"
        "• 📍 Plug-in 1-4 (Rak penyimpanan)\n"
        "• 📍 Showcase 1-4 (Etalage display)\n\n"
        "Pilih menu di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

# ===================== FLASK WEBHOOK =====================
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    """Handle incoming webhook updates"""
    if bot_app:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        asyncio.run_coroutine_threadsafe(
            bot_app.process_update(update), 
            bot_app.loop
        )
    return 'OK', 200

@app.route('/')
def index():
    return 'Bot is running!', 200

def setup_webhook():
    """Setup webhook untuk bot"""
    import requests
    # Ganti dengan URL cloud Anda
    CLOUD_URL = "https://expired-bot-xxxxx.a.run.app"  # GANTI DENGAN URL CLOUD ANDA!
    webhook_url = f"{CLOUD_URL}/{TOKEN}"
    
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    data = {"url": webhook_url}
    response = requests.post(url, json=data)
    print("Setup Webhook:", response.json())

# ===================== MAIN =====================
def main():
    global bot_app
    
    print("="*50)
    print("🏪 BOT EXPIRED PRO - WEBHOOK MODE")
    print("="*50)
    
    # Setup bot application
    bot_app = ApplicationBuilder().token(TOKEN).build()
    
    # Job queue untuk notifikasi otomatis
    job_queue = bot_app.job_queue
    if job_queue:
        job_queue.run_repeating(cek_expired, interval=21600, first=10)
        print("⏰ Notifikasi otomatis: AKTIF")
    
    # Register handlers
    bot_app.add_handler(CommandHandler('start', start))
    
    # Setup webhook
    setup_webhook()
    
    print("✅ Bot siap dengan webhook!")
    print("="*50)
    
    # Jalankan Flask app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    main()
