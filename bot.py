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

# ... (sisa kode bot Anda) ...
