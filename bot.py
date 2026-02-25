import os
import csv
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

TOKEN = os.getenv("TOKEN")

DATA_FILE = "data.csv"

# ================== STATE ==================
INPUT_NAMA, INPUT_EXPIRED = range(2)

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["➕ Tambah Data"],
        ["📋 Lihat Data"],
        ["🗑 Hapus Data"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🤖 Bot Monitoring Expired\n\nPilih menu:",
        reply_markup=reply_markup
    )

# ================== TAMBAH DATA ==================
async def tambah_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Masukkan nama produk:",
        reply_markup=ReplyKeyboardRemove()
    )
    return INPUT_NAMA

async def input_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nama"] = update.message.text
    await update.message.reply_text("Masukkan tanggal expired (format: YYYY-MM-DD)")
    return INPUT_EXPIRED

async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = context.user_data["nama"]
    expired = update.message.text

    with open(DATA_FILE, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([nama, expired])

    await update.message.reply_text("✅ Data berhasil disimpan")
    return ConversationHandler.END

# ================== LIHAT DATA ==================
async def lihat_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(DATA_FILE):
        await update.message.reply_text("Belum ada data.")
        return

    today = datetime.today()
    pesan = "📋 DATA EXPIRED:\n\n"

    with open(DATA_FILE, mode="r") as file:
        reader = csv.reader(file)
        for row in reader:
            nama, expired = row
            exp_date = datetime.strptime(expired, "%Y-%m-%d")
            sisa_hari = (exp_date - today).days

            pesan += f"• {nama}\n"
            pesan += f"  Exp: {expired}\n"
            pesan += f"  Sisa: {sisa_hari} hari\n\n"

    await update.message.reply_text(pesan)

# ================== HAPUS DATA ==================
async def hapus_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(DATA_FILE):
        await update.message.reply_text("Belum ada data.")
        return

    os.remove(DATA_FILE)
    await update.message.reply_text("🗑 Semua data berhasil dihapus.")

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Tambah Data$"), tambah_data)],
        states={
            INPUT_NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_nama)],
            INPUT_EXPIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_expired)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^📋 Lihat Data$"), lihat_data))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Hapus Data$"), hapus_data))

    print("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
