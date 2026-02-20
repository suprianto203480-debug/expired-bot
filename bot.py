import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = os.getenv("8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw")

# States
NAMA, TANGGAL, LOKASI = range(3)

data_produk = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Selamat datang di Bot Monitoring Expired\n\n"
        "Ketik /tambah untuk menambahkan produk."
    )

async def tambah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Masukkan nama produk:")
    return NAMA

async def nama_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nama"] = update.message.text
    await update.message.reply_text("Masukkan tanggal expired (format: DD-MM-YYYY):")
    return TANGGAL

async def tanggal_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tanggal"] = update.message.text
    await update.message.reply_text("Masukkan lokasi penyimpanan:")
    return LOKASI

async def lokasi_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lokasi"] = update.message.text

    produk = {
        "nama": context.user_data["nama"],
        "tanggal": context.user_data["tanggal"],
        "lokasi": context.user_data["lokasi"],
    }

    data_produk.append(produk)

    await update.message.reply_text(
        f"✅ Produk berhasil ditambahkan!\n\n"
        f"Nama: {produk['nama']}\n"
        f"Expired: {produk['tanggal']}\n"
        f"Lokasi: {produk['lokasi']}"
    )

    return ConversationHandler.END

async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data_produk:
        await update.message.reply_text("Belum ada produk.")
        return

    pesan = "📋 Daftar Produk:\n\n"
    for i, p in enumerate(data_produk, 1):
        pesan += (
            f"{i}. {p['nama']}\n"
            f"   Expired: {p['tanggal']}\n"
            f"   Lokasi: {p['lokasi']}\n\n"
        )

    await update.message.reply_text(pesan)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("tambah", tambah)],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_produk)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_produk)],
            LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi_produk)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_produk))
    app.add_handler(conv_handler)

    print("Bot sedang berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()





