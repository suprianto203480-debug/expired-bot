import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ✅ PERBAIKAN 1: Token langsung diassign, bukan pakai os.getenv()
TOKEN = "8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw"  # Gunakan token baru dari BotFather

# States
NAMA, TANGGAL, LOKASI = range(3)

# Simpan data di dictionary per user (lebih baik daripada list global)
data_produk = {}  # {user_id: [produk1, produk2, ...]}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Inisialisasi data user jika belum ada
    if user_id not in data_produk:
        data_produk[user_id] = []
    
    await update.message.reply_text(
        "🔥 *Monitoring Expired Produk* 🔥\n\n"
        "Perintah yang tersedia:\n"
        "/tambah - Tambah produk baru\n"
        "/list - Lihat semua produk\n"
        "/hapus - Hapus produk\n\n"
        "📍 Fitur Lokasi tersedia!",
        parse_mode="Markdown"
    )

async def tambah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 Masukkan *nama produk*:", parse_mode="Markdown")
    return NAMA

async def nama_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nama"] = update.message.text
    await update.message.reply_text("📅 Masukkan *tanggal expired* (format: YYYY-MM-DD):\nContoh: 2026-12-31", parse_mode="Markdown")
    return TANGGAL

async def tanggal_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Validasi format tanggal
    tanggal = update.message.text
    try:
        # Cek format tanggal (sederhana)
        datetime.strptime(tanggal, '%Y-%m-%d')
        context.user_data["tanggal"] = tanggal
        await update.message.reply_text("📍 Masukkan *lokasi penyimpanan*:\nContoh: Rak A3, Gudang, Kulkas", parse_mode="Markdown")
        return LOKASI
    except:
        await update.message.reply_text("❌ Format salah! Gunakan YYYY-MM-DD\nContoh: 2026-12-31")
        return TANGGAL

async def lokasi_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    
    user_id = update.effective_user.id
    context.user_data["lokasi"] = update.message.text

    produk = {
        "nama": context.user_data["nama"],
        "tanggal": context.user_data["tanggal"],
        "lokasi": context.user_data["lokasi"],
    }

    # Simpan ke data user
    if user_id not in data_produk:
        data_produk[user_id] = []
    data_produk[user_id].append(produk)

    # Format tanggal untuk tampilan
    expired_date = datetime.strptime(produk['tanggal'], '%Y-%m-%d').date()
    
    await update.message.reply_text(
        f"✅ *Produk berhasil ditambahkan!*\n\n"
        f"📦 *Nama:* {produk['nama']}\n"
        f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
        f"📍 *Lokasi:* {produk['lokasi']}",
        parse_mode="Markdown"
    )

    # Bersihkan user_data
    context.user_data.clear()
    return ConversationHandler.END

async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    
    user_id = update.effective_user.id
    produk_list = data_produk.get(user_id, [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Belum ada produk*\n\nGunakan /tambah untuk menambahkan produk.",
            parse_mode="Markdown"
        )
        return

    # Urutkan berdasarkan tanggal
    produk_list.sort(key=lambda x: x['tanggal'])
    
    today = datetime.now().date()
    pesan = "📋 *DAFTAR PRODUK*\n\n"
    
    for i, p in enumerate(produk_list, 1):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        selisih = (expired_date - today).days
        
        if selisih < 0:
            status = "❌ EXPIRED"
        elif selisih <= 7:
            status = f"⚠️ Sisa {selisih} hari"
        else:
            status = f"✅ {selisih} hari"
        
        pesan += (
            f"{i}. *{p['nama']}*\n"
            f"   📅 {expired_date.strftime('%d %b %Y')} - {status}\n"
            f"   📍 {p['lokasi']}\n\n"
        )
    
    pesan += f"Total: {len(produk_list)} produk"
    await update.message.reply_text(pesan, parse_mode="Markdown")

async def hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    produk_list = data_produk.get(user_id, [])
    
    if not produk_list:
        await update.message.reply_text("📭 Tidak ada produk untuk dihapus.")
        return
    
    pesan = "🗑 *HAPUS PRODUK*\n\nKetik nomor produk yang ingin dihapus:\n\n"
    for i, p in enumerate(produk_list, 1):
        pesan += f"{i}. {p['nama']} - {p['tanggal']} ({p['lokasi']})\n"
    
    pesan += "\nKetik 0 untuk batal"
    await update.message.reply_text(pesan, parse_mode="Markdown")
    
    # Simpan daftar produk di context untuk proses hapus
    context.user_data['daftar_hapus'] = produk_list
    return HAPUS

async def proses_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        pilihan = int(update.message.text)
        
        if pilihan == 0:
            await update.message.reply_text("🚫 Penghapusan dibatalkan.")
            return ConversationHandler.END
        
        produk_list = context.user_data.get('daftar_hapus', [])
        
        if 1 <= pilihan <= len(produk_list):
            produk_hapus = produk_list.pop(pilihan - 1)
            data_produk[user_id] = produk_list
            
            await update.message.reply_text(
                f"✅ *Produk dihapus!*\n\n"
                f"Nama: {produk_hapus['nama']}\n"
                f"Tanggal: {produk_hapus['tanggal']}\n"
                f"Lokasi: {produk_hapus['lokasi']}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Nomor tidak valid!")
            
    except ValueError:
        await update.message.reply_text("❌ Masukkan nomor yang valid!")
    
    return ConversationHandler.END

async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Perintah dibatalkan.")
    return ConversationHandler.END

def main():
    # ✅ PASTIKAN TOKEN DI SINI BENAR
    print(f"Token yang digunakan: {TOKEN[:10]}...")  # Cek token (hanya 10 karakter pertama)
    
    app = ApplicationBuilder().token(TOKEN).build()

    # Conversation handler untuk tambah produk
    tambah_conv = ConversationHandler(
        entry_points=[CommandHandler("tambah", tambah)],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_produk)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_produk)],
            LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi_produk)],
        },
        fallbacks=[CommandHandler("batal", batal)],
    )

    # Handler untuk hapus produk
    hapus_conv = ConversationHandler(
        entry_points=[CommandHandler("hapus", hapus)],
        states={
            HAPUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, proses_hapus)],
        },
        fallbacks=[CommandHandler("batal", batal)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_produk))
    app.add_handler(tambah_conv)
    app.add_handler(hapus_conv)

    print("✅ Bot Monitoring Expired + Lokasi started...")
    print("📱 Cek Telegram Anda sekarang!")
    app.run_polling()

# Tambahkan import datetime
from datetime import datetime
# Tambahkan state HAPUS
HAPUS = 3

if __name__ == "__main__":
    main()
