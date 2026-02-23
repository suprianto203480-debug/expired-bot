"""
File: simple_bot.py
Bot Telegram versi sederhana untuk testing
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============= KONFIGURASI =============
TOKEN = os.getenv("BOT_TOKEN")
# =======================================

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

print("🚀 Simple Bot Starting...")
print(f"BOT_TOKEN: {'✅ SET' if TOKEN else '❌ NOT SET'}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler sederhana untuk /start"""
    user = update.effective_user
    print(f"📩 /start dari user: {user.first_name} (ID: {user.id})")
    
    await update.message.reply_text(
        f"👋 Halo {user.first_name}!\n\n"
        f"✅ Bot sederhana berjalan!\n"
        f"📊 Ini adalah versi testing."
    )

def main():
    """Menjalankan bot"""
    print("🤖 Memulai bot...")
    
    # Buat aplikasi
    app = Application.builder().token(TOKEN).build()
    
    # Tambah handler
    app.add_handler(CommandHandler("start", start))
    
    print("✅ Bot siap! Menjalankan polling...")
    # Jalankan bot
    app.run_polling()

if __name__ == "__main__":
    main()
