import os
import logging
import psycopg2
import psycopg2.extras
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

logging.basicConfig(level=logging.INFO)

if not TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan di Environment Variables!")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL tidak ditemukan di Environment Variables!")

# ================= DATABASE =================
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo!\n\n"
        "Kirim UPC atau SKU untuk mencari produk."
    )

# ================= SCAN =================
async def scan_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_code = update.message.text.strip()

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("""
            SELECT dept, sku, deskripsi
            FROM products
            WHERE upc::text = %s
               OR sku::text = %s
            LIMIT 1
        """, (input_code, input_code))

        product = cur.fetchone()

        if product:
            # Simpan history
            cur.execute("""
                INSERT INTO scans (input_code, sku, deskripsi)
                VALUES (%s, %s, %s)
            """, (input_code, product["sku"], product["deskripsi"]))

            conn.commit()

            await update.message.reply_text(
                f"✅ Produk ditemukan:\n\n"
                f"📦 {product['deskripsi']}\n"
                f"🏷 SKU: {product['sku']}\n"
                f"🏬 Dept: {product['dept']}"
            )
        else:
            await update.message.reply_text("❌ Produk tidak ditemukan.")

        cur.close()
        conn.close()

    except Exception as e:
        print("ERROR DATABASE:", e)
        await update.message.reply_text("⚠️ Database error.")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, scan_product))

    print("🚀 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
