import os
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

# ================= DATABASE FUNCTION =================
def get_connection():
    return psycopg2.connect(DATABASE_URL)

def search_product(keyword):
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = """
        SELECT sku, upc, nama_produk, expired_date, lokasi
        FROM products
        WHERE 
            sku ILIKE %s OR
            upc ILIKE %s OR
            nama_produk ILIKE %s
        LIMIT 10
        """

        value = f"%{keyword}%"

        cur.execute(query, (value, value, value))
        rows = cur.fetchall()

        cur.close()
        conn.close()

        return rows

    except Exception as e:
        print("Database Error:", e)
        return None

# ================= BOT HANDLER =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo!\n\nKirim UPC / SKU / Nama produk untuk mencari data."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()

    results = search_product(keyword)

    if results is None:
        await update.message.reply_text("⚠️ Database error.")
        return

    if len(results) == 0:
        await update.message.reply_text("❌ Produk tidak ditemukan.")
        return

    response = "🔎 HASIL PENCARIAN:\n\n"

    for row in results:
        sku, upc, nama, expired, lokasi = row
        response += (
            f"📦 Nama: {nama}\n"
            f"🔖 SKU: {sku}\n"
            f"🏷 UPC: {upc}\n"
            f"📅 Expired: {expired}\n"
            f"📍 Lokasi: {lokasi}\n"
            f"----------------------\n"
        )

    await update.message.reply_text(response)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
