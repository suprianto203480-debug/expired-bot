import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from datetime import datetime

# ✅ TOKEN ANDA (SUDAH BENAR)
TOKEN = "8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw"

# States untuk ConversationHandler
NAMA, TANGGAL, LOKASI, HAPUS = range(4)

# Database sederhana (dalam memory)
data_produk = {}  # {user_id: [produk1, produk2, ...]}

# ===================== HANDLER START =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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

# ===================== HANDLER TAMBAH PRODUK =====================
async def tambah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai proses tambah produk"""
    await update.message.reply_text(
        "📦 *Tambah Produk Baru*\n\n"
        "Silakan masukkan *nama produk*:",
        parse_mode="Markdown"
    )
    return NAMA

async def nama_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima nama produk"""
    context.user_data['nama'] = update.message.text
    await update.message.reply_text(
        "📅 Sekarang masukkan *tanggal expired*\n"
        "Format: YYYY-MM-DD\n"
        "Contoh: 2026-12-31",
        parse_mode="Markdown"
    )
    return TANGGAL

async def tanggal_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima tanggal expired"""
    tanggal_str = update.message.text
    
    # Validasi format tanggal
    try:
        datetime.strptime(tanggal_str, '%Y-%m-%d')
        context.user_data['tanggal'] = tanggal_str
        await update.message.reply_text(
            "📍 Terakhir, masukkan *lokasi penyimpanan*:\n"
            "Contoh: Rak A3, Lemari Es, Gudang Belakang",
            parse_mode="Markdown"
        )
        return LOKASI
    except ValueError:
        await update.message.reply_text(
            "❌ Format tanggal salah! Gunakan YYYY-MM-DD\n"
            "Contoh: 2026-12-31\n\n"
            "Silakan coba lagi:"
        )
        return TANGGAL

async def lokasi_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menerima lokasi dan menyimpan produk"""
    user_id = update.effective_user.id
    lokasi = update.message.text
    
    # Buat produk baru
    produk_baru = {
        "nama": context.user_data['nama'],
        "tanggal": context.user_data['tanggal'],
        "lokasi": lokasi
    }
    
    # Simpan ke database
    if user_id not in data_produk:
        data_produk[user_id] = []
    data_produk[user_id].append(produk_baru)
    
    # Konfirmasi
    expired_date = datetime.strptime(produk_baru['tanggal'], '%Y-%m-%d').date()
    await update.message.reply_text(
        f"✅ *Produk berhasil ditambahkan!*\n\n"
        f"📦 *Nama:* {produk_baru['nama']}\n"
        f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
        f"📍 *Lokasi:* {produk_baru['lokasi']}",
        parse_mode="Markdown"
    )
    
    # Bersihkan data sementara
    context.user_data.clear()
    return ConversationHandler.END

# ===================== HANDLER LIST PRODUK =====================
async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan semua produk"""
    user_id = update.effective_user.id
    produk_list = data_produk.get(user_id, [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Belum ada produk*\n\n"
            "Gunakan /tambah untuk menambahkan produk.",
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

# ===================== HANDLER HAPUS PRODUK =====================
async def hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memulai proses hapus produk"""
    user_id = update.effective_user.id
    produk_list = data_produk.get(user_id, [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Tidak ada produk untuk dihapus.*",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # Tampilkan daftar produk
    pesan = "🗑 *HAPUS PRODUK*\n\nKetik *nomor* produk yang ingin dihapus:\n\n"
    for i, p in enumerate(produk_list, 1):
        pesan += f"{i}. {p['nama']} - {p['tanggal']} ({p['lokasi']})\n"
    
    pesan += "\nKetik 0 untuk batal"
    await update.message.reply_text(pesan, parse_mode="Markdown")
    
    # Simpan daftar produk di context
    context.user_data['daftar_hapus'] = produk_list.copy()
    return HAPUS

async def proses_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Memproses penghapusan produk"""
    user_id = update.effective_user.id
    
    try:
        pilihan = int(update.message.text)
        
        if pilihan == 0:
            await update.message.reply_text("🚫 Penghapusan dibatalkan.")
            context.user_data.clear()
            return ConversationHandler.END
        
        produk_list = context.user_data.get('daftar_hapus', [])
        
        if 1 <= pilihan <= len(produk_list):
            # Hapus produk
            produk_hapus = data_produk[user_id].pop(pilihan - 1)
            
            await update.message.reply_text(
                f"✅ *Produk berhasil dihapus!*\n\n"
                f"Nama: {produk_hapus['nama']}\n"
                f"Tanggal: {produk_hapus['tanggal']}\n"
                f"Lokasi: {produk_hapus['lokasi']}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ Nomor tidak valid! Silakan coba lagi.")
            
    except ValueError:
        await update.message.reply_text("❌ Masukkan nomor yang valid (angka)!")
    
    context.user_data.clear()
    return ConversationHandler.END

# ===================== HANDLER BATAL =====================
async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membatalkan percakapan"""
    await update.message.reply_text("🚫 Perintah dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END

# ===================== MAIN =====================
def main():
    """Fungsi utama menjalankan bot"""
    print("🚀 Memulai Bot Monitoring Expired...")
    print(f"🤖 Token: {TOKEN[:10]}...")
    
    # Buat aplikasi
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Conversation handler untuk TAMBAH produk
    tambah_conv = ConversationHandler(
        entry_points=[CommandHandler('tambah', tambah)],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_produk)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_produk)],
            LOKASI: [MessageHandler(filters.TEXT & ~filters.COMMAND, lokasi_produk)],
        },
        fallbacks=[CommandHandler('batal', batal)]
    )
    
    # Conversation handler untuk HAPUS produk
    hapus_conv = ConversationHandler(
        entry_points=[CommandHandler('hapus', hapus)],
        states={
            HAPUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, proses_hapus)],
        },
        fallbacks=[CommandHandler('batal', batal)]
    )
    
    # Daftarkan semua handler
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('list', list_produk))
    app.add_handler(tambah_conv)
    app.add_handler(hapus_conv)
    
    print("✅ Bot siap! Cek Telegram sekarang...")
    print("📱 Kirim /start ke bot Anda")
    
    # Jalankan bot
    app.run_polling()

if __name__ == "__main__":
    main()
