import os
import logging
import psycopg2
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ================= DATABASE FUNCTION =================
def get_connection():
    return psycopg2.connect(DATABASE_URL)

# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo!\n\n"
        "Silakan kirim:\n"
        "- UPC (barcode panjang)\n"
        "- SKU (kode pendek)\n\n"
        "Bot akan mencari di database 🔎"
    )

# ================= SCAN FUNCTION =================
async def scan_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_code = update.message.text.strip()

    if not input_code:
        return

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Query fleksibel (UPC atau SKU)
        cur.execute("""
            SELECT dept, sku, deskripsi 
            FROM products
            WHERE upc::text = %s
               OR sku::text = %s
            LIMIT 1
        """, (input_code, input_code))

        result = cur.fetchone()

        if result:
            dept, sku, deskripsi = result

            # Simpan ke tabel scans
            cur.execute("""
                INSERT INTO scans (input_code, sku, deskripsi)
                VALUES (%s, %s, %s)
            """, (input_code, sku, deskripsi))

            conn.commit()

            await update.message.reply_text(
                f"✅ Produk ditemukan:\n\n"
                f"📦 {deskripsi}\n"
                f"🏷 SKU: {sku}\n"
                f"🏬 Dept: {dept}"
            )
        else:
            await update.message.reply_text("❌ Produk tidak ditemukan.")

        cur.close()
        conn.close()

    except Exception as e:
        print("DATABASE ERROR:", e)
        await update.message.reply_text("⚠️ Terjadi kesalahan koneksi database.")

# ================= MAIN =================
def main():
    if not TOKEN:
        print("BOT_TOKEN tidak ditemukan!")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, scan_product))

    print("🚀 Bot berjalan dengan PostgreSQL...")
    app.run_polling()

if __name__ == "__main__":
    main()
