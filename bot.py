import os
import logging
import pandas as pd
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== CONFIG ==================
TOKEN = os.getenv("BOT_TOKEN")  # Ambil dari Railway ENV
DATA_FILE = "data.xlsx"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ================== LOAD DATA ==================
def load_data():
    try:
        df = pd.read_excel(DATA_FILE)
        return df
    except:
        return None

# ================== COMMAND START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo!\n\n"
        "Silakan kirim atau scan barcode untuk mencari produk."
    )

# ================== SCAN BARCODE ==================
async def scan_barcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    barcode = update.message.text.strip()
    df = load_data()

    if df is None:
        await update.message.reply_text("⚠️ Database tidak ditemukan.")
        return

    result = df[df["UPC"].astype(str) == barcode]

    if result.empty:
        await update.message.reply_text("❌ Produk tidak ditemukan.")
    else:
        row = result.iloc[0]
        await update.message.reply_text(
            f"✅ Produk ditemukan:\n\n"
            f"📦 Nama: {row['Nama Produk']}\n"
            f"🏷 Harga: {row['Harga']}\n"
            f"📍 Lokasi: {row['Lokasi']}"
        )

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, scan_barcode))

    print("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
