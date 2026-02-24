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

# ================= DATABASE =================
def get_connection():
    return psycopg2.connect(DATABASE_URL)

def search_product(keyword, dept_filter=None):
    try:
        conn = get_connection()
        cur = conn.cursor()

        value = f"%{keyword}%"

        if dept_filter:
            query = """
            SELECT dept, sku, deskripsi, upc
            FROM products
            WHERE dept = %s AND (
                CAST(sku AS TEXT) ILIKE %s OR
                CAST(upc AS TEXT) ILIKE %s OR
                deskripsi ILIKE %s
            )
            ORDER BY dept, sku
            LIMIT 10
            """
            cur.execute(query, (dept_filter, value, value, value))
        else:
            query = """
            SELECT dept, sku, deskripsi, upc
            FROM products
            WHERE 
                CAST(sku AS TEXT) ILIKE %s OR
                CAST(upc AS TEXT) ILIKE %s OR
                deskripsi ILIKE %s
            ORDER BY dept, sku
            LIMIT 10
            """
            cur.execute(query, (value, value, value))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return rows

    except Exception as e:
        print("Database Error:", e)
        return None

# ================= COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo!\n\n"
        "Kirim:\n"
        "SKU / UPC / Nama produk\n\n"
        "Atau gunakan format:\n"
        "dept:97 ayam\n\n"
        "Gunakan /help untuk bantuan."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 CARA PAKAI BOT:\n\n"
        "1️⃣ Cari normal:\n"
        "97236290\n"
        "atau\n"
        "ayam\n\n"
        "2️⃣ Filter berdasarkan Dept:\n"
        "dept:97 ayam\n\n"
        "Format:\n"
        "dept:<kode_dept> <kata_kunci>"
    )

# ================= MESSAGE =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    dept_filter = None
    keyword = text

    # Cek apakah pakai filter dept
    if text.lower().startswith("dept:"):
        try:
            parts = text.split(" ", 1)
            dept_part = parts[0]
            keyword = parts[1]

            dept_filter = dept_part.replace("dept:", "").strip()
        except:
            await update.message.reply_text("❌ Format salah. Contoh: dept:97 ayam")
            return

    results = search_product(keyword, dept_filter)

    if results is None:
        await update.message.reply_text("⚠️ Database error.")
        return

    if len(results) == 0:
        await update.message.reply_text("❌ Produk tidak ditemukan.")
        return

    response = "🔎 HASIL PENCARIAN:\n\n"

    for i, row in enumerate(results, start=1):
        dept, sku, deskripsi, upc = row

        response += (
            f"{i}️⃣\n"
            f"🏬 Dept: {dept}\n"
            f"🔖 SKU: {sku}\n"
            f"📦 Nama: {deskripsi}\n"
            f"🏷 UPC: {upc}\n"
            f"----------------------\n"
        )

    await update.message.reply_text(response)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
