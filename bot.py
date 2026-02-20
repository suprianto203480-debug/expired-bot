import os
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler,
    JobQueue
)
from telegram.constants import ParseMode

# ===================== KONFIGURASI =====================
TOKEN = "8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw"
DATA_FILE = "produk_database.json"

# States untuk ConversationHandler
NAMA, TANGGAL, TIPE_LOKASI, PLUGIN, SHOWCASE, KATEGORI = range(6)

# ===================== DATABASE JSON =====================
def load_data():
    """Load data dari file JSON"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    """Save data ke file JSON"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user_data(user_id):
    """Get data spesifik user"""
    data = load_data()
    return data.get(str(user_id), {"produk": [], "notifikasi": {}})

def save_user_data(user_id, user_data):
    """Save data spesifik user"""
    data = load_data()
    data[str(user_id)] = user_data
    save_data(data)

# ===================== NOTIFIKASI OTOMATIS =====================
async def cek_expired(context: ContextTypes.DEFAULT_TYPE):
    """Cek produk expired dan kirim notifikasi otomatis"""
    print(f"🔔 Cek expired: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    data = load_data()
    today = datetime.now().date()
    
    for user_id_str, user_data in data.items():
        produk_list = user_data.get("produk", [])
        notifikasi_terkirim = user_data.get("notifikasi", {})
        notifikasi_baru = {}
        
        for produk in produk_list:
            try:
                expired_date = datetime.strptime(produk['tanggal'], '%Y-%m-%d').date()
                selisih = (expired_date - today).days
                produk_id = f"{produk['nama']}_{produk['tanggal']}"
                
                # NOTIFIKASI H-7
                if selisih == 7:
                    if notifikasi_terkirim.get(produk_id) != 7:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=(
                                f"⚠️ *PERINGATAN H-7!*\n\n"
                                f"📦 *Produk:* {produk['nama']}\n"
                                f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                                f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                                f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                                f"⏰ *Tersisa 7 hari lagi!*\n"
                                f"🔔 Segera cek stok Anda!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                        notifikasi_baru[produk_id] = 7
                
                # NOTIFIKASI H-3
                elif selisih == 3:
                    if notifikasi_terkirim.get(produk_id) != 3:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=(
                                f"⚠️ *PERINGATAN H-3!*\n\n"
                                f"📦 *Produk:* {produk['nama']}\n"
                                f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                                f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                                f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                                f"⏰ *Tersisa 3 hari lagi!*\n"
                                f"🔔 Segera tindak lanjuti!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                        notifikasi_baru[produk_id] = 3
                
                # NOTIFIKASI H-1
                elif selisih == 1:
                    if notifikasi_terkirim.get(produk_id) != 1:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=(
                                f"⚠️ *PERINGATAN H-1!*\n\n"
                                f"📦 *Produk:* {produk['nama']}\n"
                                f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                                f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                                f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                                f"⏰ *BESOK EXPIRED!*\n"
                                f"🔔 Segera gunakan atau pindahkan!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                        notifikasi_baru[produk_id] = 1
                
                # NOTIFIKASI EXPIRED
                elif selisih == 0:
                    if notifikasi_terkirim.get(produk_id) != "expired_hari_ini":
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=(
                                f"❌ *EXPIRED HARI INI!*\n\n"
                                f"📦 *Produk:* {produk['nama']}\n"
                                f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                                f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                                f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                                f"⚠️ *Produk sudah expired hari ini!*"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                        notifikasi_baru[produk_id] = "expired_hari_ini"
                
                elif selisih < 0:
                    if notifikasi_terkirim.get(produk_id) != "expired":
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=(
                                f"❌ *PRODUK SUDAH EXPIRED!*\n\n"
                                f"📦 *Produk:* {produk['nama']}\n"
                                f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                                f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                                f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                                f"⚠️ *Sudah {abs(selisih)} hari expired!*\n"
                                f"🔔 Segera buang/ganti produk!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                        notifikasi_baru[produk_id] = "expired"
                
                else:
                    if produk_id in notifikasi_terkirim:
                        notifikasi_baru[produk_id] = notifikasi_terkirim[produk_id]
                        
            except Exception as e:
                print(f"Error notifikasi: {e}")
        
        # Update status notifikasi
        user_data["notifikasi"] = notifikasi_baru
        save_user_data(user_id_str, user_data)

# ===================== MENU UTAMA =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu utama dengan tombol interaktif"""
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="tambah")],
        [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="list")],
        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="hapus")],
        [InlineKeyboardButton("📊 STATISTIK", callback_data="stats")],
        [InlineKeyboardButton("📍 CEK LOKASI", callback_data="lokasi")],
        [InlineKeyboardButton("❓ BANTUAN", callback_data="bantuan")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏪 *MONITORING EXPIRED PRO V3* 🏪\n\n"
        "Sistem manajemen expired dengan *lokasi bertingkat*:\n"
        "• 📍 Plug-in 1-4 (Rak penyimpanan)\n"
        "• 📍 Showcase 1-4 (Etalage display)\n\n"
        "Pilih menu di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

# ===================== CALLBACK HANDLER =====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua tombol callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "tambah":
        await query.edit_message_text(
            "📦 *TAMBAH PRODUK BARU*\n\n"
            "Silakan masukkan *nama produk*:",
            parse_mode=ParseMode.MARKDOWN
        )
        return NAMA
    
    elif query.data == "list":
        await list_produk(update, context)
    
    elif query.data == "hapus":
        await hapus_mulai(update, context)
    
    elif query.data == "stats":
        await statistik(update, context)
    
    elif query.data == "lokasi":
        await cek_lokasi(update, context)
    
    elif query.data == "bantuan":
        await bantuan(update, context)
    
    elif query.data.startswith("plugin_"):
        # Pilih nomor plug-in
        nomor = query.data.replace("plugin_", "")
        context.user_data['lokasi_tipe'] = "Plug-in"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Plug-in {nomor}"
        await pilih_kategori(update, context)
    
    elif query.data.startswith("showcase_"):
        # Pilih nomor showcase
        nomor = query.data.replace("showcase_", "")
        context.user_data['lokasi_tipe'] = "Showcase"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Showcase {nomor}"
        await pilih_kategori(update, context)
    
    elif query.data.startswith("kategori_"):
        kategori = query.data.replace("kategori_", "")
        kategori_map = {
            "susu": "🥛 Susu",
            "daging": "🥩 Daging",
            "sayur": "🥦 Sayur",
            "roti": "🍞 Roti",
            "minuman": "🧃 Minuman",
            "lain": "📦 Lainnya"
        }
        context.user_data['kategori'] = kategori_map.get(kategori, "📦 Lainnya")
        await simpan_produk(update, context)

# ===================== TAMBAH PRODUK =====================
async def nama_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima nama produk"""
    context.user_data['nama'] = update.message.text
    await update.message.reply_text(
        "📅 Masukkan *tanggal expired* (YYYY-MM-DD):\n"
        "Contoh: 2026-12-31",
        parse_mode=ParseMode.MARKDOWN
    )
    return TANGGAL

async def tanggal_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima tanggal expired"""
    try:
        datetime.strptime(update.message.text, '%Y-%m-%d')
        context.user_data['tanggal'] = update.message.text
        
        # Pilih tipe lokasi
        keyboard = [
            [InlineKeyboardButton("📦 PLUG-IN (Rak)", callback_data="tipe_plugin")],
            [InlineKeyboardButton("🪟 SHOWCASE (Etalase)", callback_data="tipe_showcase")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📍 *PILIH TIPE LOKASI:*\n\n"
            "• Plug-in: Rak penyimpanan stok\n"
            "• Showcase: Etalage display",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return TIPE_LOKASI
    except:
        await update.message.reply_text(
            "❌ Format salah! Gunakan YYYY-MM-DD\n"
            "Contoh: 2026-12-31"
        )
        return TANGGAL

async def tipe_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih tipe lokasi"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "tipe_plugin":
        # Pilih nomor plug-in
        keyboard = [
            [InlineKeyboardButton("📦 Plug-in 1", callback_data="plugin_1")],
            [InlineKeyboardButton("📦 Plug-in 2", callback_data="plugin_2")],
            [InlineKeyboardButton("📦 Plug-in 3", callback_data="plugin_3")],
            [InlineKeyboardButton("📦 Plug-in 4", callback_data="plugin_4")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH NOMOR PLUG-IN:*\n\n"
            "Pilih rak penyimpanan:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif query.data == "tipe_showcase":
        # Pilih nomor showcase
        keyboard = [
            [InlineKeyboardButton("🪟 Showcase 1", callback_data="showcase_1")],
            [InlineKeyboardButton("🪟 Showcase 2", callback_data="showcase_2")],
            [InlineKeyboardButton("🪟 Showcase 3", callback_data="showcase_3")],
            [InlineKeyboardButton("🪟 Showcase 4", callback_data="showcase_4")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH NOMOR SHOWCASE:*\n\n"
            "Pilih etalage display:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    return PLUGIN  # State untuk menunggu pilihan

async def pilih_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih kategori produk"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🥛 Susu", callback_data="kategori_susu")],
        [InlineKeyboardButton("🥩 Daging", callback_data="kategori_daging")],
        [InlineKeyboardButton("🥦 Sayur", callback_data="kategori_sayur")],
        [InlineKeyboardButton("🍞 Roti", callback_data="kategori_roti")],
        [InlineKeyboardButton("🧃 Minuman", callback_data="kategori_minuman")],
        [InlineKeyboardButton("📦 Lainnya", callback_data="kategori_lain")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    lokasi = context.user_data['lokasi_detail']
    await query.edit_message_text(
        f"📍 *Lokasi:* {lokasi}\n\n"
        f"🏷 *PILIH KATEGORI PRODUK:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return KATEGORI

async def simpan_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan produk ke database"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    produk = {
        "nama": context.user_data['nama'],
        "tanggal": context.user_data['tanggal'],
        "lokasi_tipe": context.user_data['lokasi_tipe'],
        "lokasi_nomor": context.user_data['lokasi_nomor'],
        "lokasi_detail": context.user_data['lokasi_detail'],
        "kategori": context.user_data['kategori'],
        "ditambahkan": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "ditambahkan_tanggal": datetime.now().strftime('%d/%m/%Y'),
        "ditambahkan_jam": datetime.now().strftime('%H:%M')
    }
    
    # Simpan ke database
    user_data = get_user_data(user_id)
    user_data["produk"].append(produk)
    save_user_data(user_id, user_data)
    
    expired_date = datetime.strptime(produk['tanggal'], '%Y-%m-%d').date()
    today = datetime.now().date()
    selisih = (expired_date - today).days
    
    if selisih < 0:
        status = "❌ EXPIRED"
    elif selisih == 0:
        status = "⚠️ EXPIRED HARI INI"
    elif selisih <= 7:
        status = f"⚠️ Sisa {selisih} hari"
    else:
        status = f"✅ {selisih} hari"
    
    await query.edit_message_text(
        f"✅ *PRODUK BERHASIL DITAMBAH!*\n\n"
        f"📦 *Nama:* {produk['nama']}\n"
        f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
        f"📊 *Status:* {status}\n"
        f"🏷 *Kategori:* {produk['kategori']}\n"
        f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
        f"⏰ *Ditambahkan:* {produk['ditambahkan_jam']} - {produk['ditambahkan_tanggal']}\n\n"
        f"🔔 Notifikasi otomatis aktif: H-7, H-3, H-1",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Tampilkan menu utama
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH LAGI", callback_data="tambah")],
        [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="list")],
        [InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "Pilih aksi selanjutnya:",
        reply_markup=reply_markup
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ===================== LIST PRODUK =====================
async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan semua produk"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Belum ada produk*\n\n"
            "Gunakan /tambah untuk menambahkan produk.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Urutkan berdasarkan tanggal (terdekat dulu)
    produk_list.sort(key=lambda x: x['tanggal'])
    
    today = datetime.now().date()
    pesan = "📋 *DAFTAR PRODUK*\n\n"
    pesan += "┌─────────────────────\n"
    
    for i, p in enumerate(produk_list, 1):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        selisih = (expired_date - today).days
        
        if selisih < 0:
            status = "❌"
        elif selisih == 0:
            status = "⚠️⚠️"
        elif selisih <= 3:
            status = "⚠️"
        elif selisih <= 7:
            status = "⚡"
        else:
            status = "✅"
        
        pesan += f"│ {i}. {status} *{p['nama']}*\n"
        pesan += f"│    📅 {expired_date.strftime('%d/%m/%Y')} ({selisih} hari)\n"
        pesan += f"│    🏷 {p['kategori']}\n"
        pesan += f"│    📍 {p['lokasi_detail']}\n"
        pesan += f"│    ⏰ {p.get('ditambahkan_jam', '-')}\n"
        pesan += "├─────────────────────\n"
    
    pesan += f"│ 📊 *Total: {len(produk_list)} produk*\n"
    pesan += "└─────────────────────"
    
    await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)

# ===================== CEK LOKASI =====================
async def cek_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek produk berdasarkan lokasi"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    # Group by lokasi
    lokasi_dict = {}
    for p in produk_list:
        lokasi = p['lokasi_detail']
        if lokasi not in lokasi_dict:
            lokasi_dict[lokasi] = []
        lokasi_dict[lokasi].append(p)
    
    pesan = "📍 *CEK PRODUK PER LOKASI*\n\n"
    
    for lokasi in sorted(lokasi_dict.keys()):
        pesan += f"*{lokasi}:* {len(lokasi_dict[lokasi])} produk\n"
        for p in lokasi_dict[lokasi]:
            expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
            pesan += f"  • {p['nama']} ({expired_date.strftime('%d/%m')})\n"
        pesan += "\n"
    
    await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)

# ===================== STATISTIK =====================
async def statistik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan statistik lengkap"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    today = datetime.now().date()
    
    # Statistik status
    aman = 0
    warning_h7 = 0
    warning_h3 = 0
    warning_h1 = 0
    expired_hari_ini = 0
    expired = 0
    
    # Statistik kategori
    kategori = {}
    
    # Statistik lokasi
    lokasi_plugin = {f"Plug-in {i}": 0 for i in range(1,5)}
    lokasi_showcase = {f"Showcase {i}": 0 for i in range(1,5)}
    
    for p in produk_list:
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        selisih = (expired_date - today).days
        
        # Status
        if selisih < 0:
            expired += 1
        elif selisih == 0:
            expired_hari_ini += 1
        elif selisih == 1:
            warning_h1 += 1
        elif selisih <= 3:
            warning_h3 += 1
        elif selisih <= 7:
            warning_h7 += 1
        else:
            aman += 1
        
        # Kategori
        kat = p.get('kategori', 'Lainnya')
        kategori[kat] = kategori.get(kat, 0) + 1
        
        # Lokasi
        if p['lokasi_detail'].startswith('Plug-in'):
            lokasi_plugin[p['lokasi_detail']] += 1
        elif p['lokasi_detail'].startswith('Showcase'):
            lokasi_showcase[p['lokasi_detail']] += 1
    
    pesan = "📊 *STATISTIK PRODUK*\n\n"
    pesan += "*STATUS EXPIRED:*\n"
    pesan += f"✅ Aman (>7 hari): {aman}\n"
    pesan += f"⚡ H-7 s/d H-4: {warning_h7}\n"
    pesan += f"⚠️ H-3 s/d H-2: {warning_h3}\n"
    pesan += f"🔥 H-1: {warning_h1}\n"
    pesan += f"⏰ Expired hari ini: {expired_hari_ini}\n"
    pesan += f"❌ Sudah expired: {expired}\n\n"
    
    pesan += "*KATEGORI:*\n"
    for kat, jml in kategori.items():
        pesan += f"{kat}: {jml}\n"
    pesan += "\n"
    
    pesan += "*LOKASI PLUG-IN:*\n"
    for lok, jml in lokasi_plugin.items():
        if jml > 0:
            pesan += f"📍 {lok}: {jml} produk\n"
    pesan += "\n"
    
    pesan += "*LOKASI SHOWCASE:*\n"
    for lok, jml in lokasi_showcase.items():
        if jml > 0:
            pesan += f"📍 {lok}: {jml} produk\n"
    pesan += "\n"
    
    pesan += f"📦 *TOTAL PRODUK: {len(produk_list)}*"
    
    await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)

# ===================== HAPUS PRODUK =====================
async def hapus_mulai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses hapus produk"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Tidak ada produk untuk dihapus*",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Tampilkan daftar dengan tombol
    keyboard = []
    for i, p in enumerate(produk_list, 1):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        keyboard.append([InlineKeyboardButton(
            f"{i}. {p['nama']} ({expired_date.strftime('%d/%m')}) - {p['lokasi_detail']}",
            callback_data=f"hapus_{i-1}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ BATAL", callback_data="batal_hapus")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🗑 *HAPUS PRODUK*\n\nPilih produk yang akan dihapus:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def hapus_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hapus produk berdasarkan callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "batal_hapus":
        await query.edit_message_text("🚫 Penghapusan dibatalkan.")
        return
    
    user_id = update.effective_user.id
    index = int(query.data.replace("hapus_", ""))
    
    user_data = get_user_data(user_id)
    produk_hapus = user_data["produk"].pop(index)
    save_user_data(user_id, user_data)
    
    await query.edit_message_text(
        f"✅ *Produk berhasil dihapus!*\n\n"
        f"Nama: {produk_hapus['nama']}\n"
        f"Lokasi: {produk_hapus['lokasi_detail']}",
        parse_mode=ParseMode.MARKDOWN
    )

# ===================== BANTUAN =====================
async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan bantuan"""
    await update.message.reply_text(
        "📚 *BANTUAN PENGGUNAAN*\n\n"
        "*PERINTAH:*\n"
        "/start - Menu utama\n"
        "/tambah - Tambah produk\n"
        "/list - Lihat semua produk\n"
        "/hapus - Hapus produk\n"
        "/stats - Statistik lengkap\n"
        "/lokasi - Cek per lokasi\n"
        "/bantuan - Bantuan ini\n\n"
        
        "*LOKASI BERTINGKAT:*\n"
        "• Plug-in 1-4 : Rak penyimpanan\n"
        "• Showcase 1-4 : Etalage display\n\n"
        
        "*NOTIFIKASI OTOMATIS:*\n"
        "⚠️ H-7 : Peringatan awal\n"
        "⚠️ H-3 : Peringatan menengah\n"
        "🔥 H-1 : Peringatan terakhir\n"
        "❌ Expired : Produk kadaluarsa\n\n"
        
        "*FORMAT TANGGAL:*\n"
        "YYYY-MM-DD\n"
        "Contoh: 2026-12-31",
        parse_mode=ParseMode.MARKDOWN
    )

# ===================== MAIN =====================
def main():
    print("="*50)
    print("🏪 BOT EXPIRED PRO V3 - LOKASI BERTINGKAT")
    print("="*50)
    print(f"🤖 Token: {TOKEN[:15]}...")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Job queue untuk notifikasi otomatis (cek setiap 6 jam)
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(cek_expired, interval=21600, first=10)  # 6 jam = 21600 detik
        print("⏰ Notifikasi otomatis: AKTIF (cek setiap 6 jam)")
        print("   • H-7, H-3, H-1, dan expired")
    
    # Conversation handler untuk TAMBAH produk
    tambah_conv = ConversationHandler(
        entry_points=[
            CommandHandler('tambah', lambda u,c: tambah_mulai(u,c) if hasattr(u, 'message') else None),
            CallbackQueryHandler(button_callback, pattern="^tambah$")
        ],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_produk)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_produk)],
            TIPE_LOKASI: [CallbackQueryHandler(tipe_lokasi, pattern="^tipe_")],
            PLUGIN: [CallbackQueryHandler(button_callback, pattern="^(plugin_|showcase_)")],
            SHOWCASE: [CallbackQueryHandler(button_callback, pattern="^(plugin_|showcase_)")],
            KATEGORI: [CallbackQueryHandler(button_callback, pattern="^kategori_")],
        },
        fallbacks=[CommandHandler('batal', lambda u,c: ConversationHandler.END)]
    )
    
    # Daftarkan semua handler
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('list', list_produk))
    app.add_handler(CommandHandler('stats', statistik))
    app.add_handler(CommandHandler('lokasi', cek_lokasi))
    app.add_handler(CommandHandler('bantuan', bantuan))
    app.add_handler(tambah_conv)
    app.add_handler(CallbackQueryHandler(hapus_produk, pattern="^hapus_"))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(batal_hapus|kembali)$"))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ BOT SIAP! Menjalankan polling...")
    print("📱 Cek Telegram Anda sekarang!")
    print("="*50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
