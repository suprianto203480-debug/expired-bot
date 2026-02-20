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

# ===================== FITUR BARU 1: EDIT PRODUK =====================
async def edit_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit produk yang sudah ada"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await query.edit_message_text(
            "📭 *Tidak ada produk untuk diedit*",
            parse_mode=ParseMode.MARKDOWN
        )
        # Tombol kembali
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
        return
    
    # Tampilkan daftar produk untuk diedit
    keyboard = []
    for i, p in enumerate(produk_list, 1):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        keyboard.append([InlineKeyboardButton(
            f"✏️ {i}. {p['nama']} ({expired_date.strftime('%d/%m')}) - {p['lokasi_detail']}",
            callback_data=f"edit_{i-1}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ BATAL", callback_data="kembali_ke_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "✏️ *EDIT PRODUK*\n\nPilih produk yang akan diedit:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def edit_produk_pilih(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih produk yang akan diedit"""
    query = update.callback_query
    await query.answer()
    
    index = int(query.data.replace("edit_", ""))
    context.user_data['edit_index'] = index
    
    # Tampilkan opsi edit
    keyboard = [
        [InlineKeyboardButton("📝 Edit Nama", callback_data=f"edit_nama_{index}")],
        [InlineKeyboardButton("📅 Edit Tanggal", callback_data=f"edit_tanggal_{index}")],
        [InlineKeyboardButton("📍 Edit Lokasi", callback_data=f"edit_lokasi_{index}")],
        [InlineKeyboardButton("🏷 Edit Kategori", callback_data=f"edit_kategori_{index}")],
        [InlineKeyboardButton("❌ BATAL", callback_data="kembali_ke_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "✏️ *PILIH BAGIAN YANG DIEDIT*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def edit_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit nama produk"""
    query = update.callback_query
    await query.answer()
    
    index = int(query.data.replace("edit_nama_", ""))
    context.user_data['edit_index'] = index
    context.user_data['edit_field'] = 'nama'
    
    await query.edit_message_text(
        "📝 Masukkan *nama baru* untuk produk:",
        parse_mode=ParseMode.MARKDOWN
    )
    return NAMA  # Reuse state NAMA

async def edit_tanggal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit tanggal expired"""
    query = update.callback_query
    await query.answer()
    
    index = int(query.data.replace("edit_tanggal_", ""))
    context.user_data['edit_index'] = index
    context.user_data['edit_field'] = 'tanggal'
    
    await query.edit_message_text(
        "📅 Masukkan *tanggal expired baru* (YYYY-MM-DD):\n"
        "Contoh: 2026-12-31",
        parse_mode=ParseMode.MARKDOWN
    )
    return TANGGAL  # Reuse state TANGGAL

async def edit_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit lokasi produk"""
    query = update.callback_query
    await query.answer()
    
    index = int(query.data.replace("edit_lokasi_", ""))
    context.user_data['edit_index'] = index
    context.user_data['edit_field'] = 'lokasi'
    
    # Pilih tipe lokasi baru
    keyboard = [
        [InlineKeyboardButton("📦 PLUG-IN (Rak)", callback_data="edit_tipe_plugin")],
        [InlineKeyboardButton("🪟 SHOWCASE (Etalase)", callback_data="edit_tipe_showcase")],
        [InlineKeyboardButton("❌ BATAL", callback_data="kembali_ke_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📍 *PILIH TIPE LOKASI BARU*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return TIPE_LOKASI  # Reuse state TIPE_LOKASI

async def edit_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit kategori produk"""
    query = update.callback_query
    await query.answer()
    
    index = int(query.data.replace("edit_kategori_", ""))
    context.user_data['edit_index'] = index
    context.user_data['edit_field'] = 'kategori'
    
    keyboard = [
        [InlineKeyboardButton("🥛 Susu", callback_data="edit_kategori_susu")],
        [InlineKeyboardButton("🥩 Daging", callback_data="edit_kategori_daging")],
        [InlineKeyboardButton("🥦 Sayur", callback_data="edit_kategori_sayur")],
        [InlineKeyboardButton("🍞 Roti", callback_data="edit_kategori_roti")],
        [InlineKeyboardButton("🧃 Minuman", callback_data="edit_kategori_minuman")],
        [InlineKeyboardButton("📦 Lainnya", callback_data="edit_kategori_lain")],
        [InlineKeyboardButton("❌ BATAL", callback_data="kembali_ke_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🏷 *PILIH KATEGORI BARU*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return KATEGORI  # Reuse state KATEGORI

async def simpan_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan hasil edit"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    index = context.user_data.get('edit_index', 0)
    field = context.user_data.get('edit_field', '')
    
    if field == 'nama':
        user_data["produk"][index]['nama'] = context.user_data.get('nama_edit', '')
        await update.message.reply_text("✅ Nama produk berhasil diupdate!")
    
    elif field == 'tanggal':
        user_data["produk"][index]['tanggal'] = context.user_data.get('tanggal_edit', '')
        await update.message.reply_text("✅ Tanggal expired berhasil diupdate!")
    
    elif field == 'kategori':
        user_data["produk"][index]['kategori'] = context.user_data.get('kategori_edit', '')
        await update.message.reply_text("✅ Kategori produk berhasil diupdate!")
    
    elif field == 'lokasi':
        user_data["produk"][index]['lokasi_tipe'] = context.user_data.get('lokasi_tipe', '')
        user_data["produk"][index]['lokasi_nomor'] = context.user_data.get('lokasi_nomor', '')
        user_data["produk"][index]['lokasi_detail'] = context.user_data.get('lokasi_detail', '')
        await update.message.reply_text("✅ Lokasi produk berhasil diupdate!")
    
    save_user_data(user_id, user_data)
    
    # Tombol kembali
    keyboard = [[InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    
    context.user_data.clear()
    return ConversationHandler.END

# ===================== FITUR BARU 2: CARI PRODUK =====================
async def cari_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cari produk berdasarkan nama"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 *CARI PRODUK*\n\n"
        "Masukkan *nama produk* yang ingin dicari:",
        parse_mode=ParseMode.MARKDOWN
    )
    return 99  # State khusus untuk pencarian

async def proses_cari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Proses pencarian produk"""
    keyword = update.message.text.lower()
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    hasil = []
    for p in produk_list:
        if keyword in p['nama'].lower():
            hasil.append(p)
    
    if not hasil:
        await update.message.reply_text(
            f"🔍 *HASIL PENCARIAN*\n\n"
            f"Tidak ditemukan produk dengan nama *{keyword}*",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        today = datetime.now().date()
        pesan = f"🔍 *HASIL PENCARIAN: {keyword}*\n\n"
        pesan += f"Ditemukan {len(hasil)} produk:\n\n"
        
        for i, p in enumerate(hasil, 1):
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
            
            pesan += f"{i}. {status} *{p['nama']}*\n"
            pesan += f"   📅 {expired_date.strftime('%d/%m/%Y')} ({selisih} hari)\n"
            pesan += f"   📍 {p['lokasi_detail']}\n\n"
        
        await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)
    
    # Tombol kembali
    keyboard = [[InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    
    return ConversationHandler.END

# ===================== FITUR BARU 3: REMINDER CUSTOM =====================
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set reminder custom untuk produk tertentu"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await query.edit_message_text(
            "📭 *Tidak ada produk untuk diatur reminder*",
            parse_mode=ParseMode.MARKDOWN
        )
        # Tombol kembali
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
        return
    
    # Tampilkan daftar produk
    keyboard = []
    for i, p in enumerate(produk_list, 1):
        keyboard.append([InlineKeyboardButton(
            f"⏰ {i}. {p['nama']}",
            callback_data=f"reminder_{i-1}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ BATAL", callback_data="kembali_ke_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⏰ *SET REMINDER*\n\nPilih produk:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def pilih_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih produk untuk reminder"""
    query = update.callback_query
    await query.answer()
    
    index = int(query.data.replace("reminder_", ""))
    context.user_data['reminder_index'] = index
    
    keyboard = [
        [InlineKeyboardButton("🔔 H-1", callback_data=f"remind_1_{index}")],
        [InlineKeyboardButton("🔔 H-2", callback_data=f"remind_2_{index}")],
        [InlineKeyboardButton("🔔 H-3", callback_data=f"remind_3_{index}")],
        [InlineKeyboardButton("🔔 H-5", callback_data=f"remind_5_{index}")],
        [InlineKeyboardButton("🔔 H-7", callback_data=f"remind_7_{index}")],
        [InlineKeyboardButton("🔔 H-14", callback_data=f"remind_14_{index}")],
        [InlineKeyboardButton("❌ BATAL", callback_data="kembali_ke_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⏰ *PILIH WAKTU REMINDER*\n\n"
        "Kapan Anda ingin diingatkan?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async simpan_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan reminder custom"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    hari = int(data[1])
    index = int(data[2])
    
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    # Simpan reminder di metadata produk
    if 'reminders' not in user_data["produk"][index]:
        user_data["produk"][index]['reminders'] = []
    
    if hari not in user_data["produk"][index]['reminders']:
        user_data["produk"][index]['reminders'].append(hari)
    
    save_user_data(user_id, user_data)
    
    await query.edit_message_text(
        f"✅ *REMINDER DISIMPAN!*\n\n"
        f"Anda akan diingatkan H-{hari} untuk produk ini.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Tombol kembali
    keyboard = [[InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== FITUR BARU 4: EXPORT DATA =====================
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export data ke format teks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await query.edit_message_text(
            "📭 *Tidak ada data untuk diexport*",
            parse_mode=ParseMode.MARKDOWN
        )
        # Tombol kembali
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
        return
    
    # Buat format export
    today = datetime.now().date()
    export_text = "📊 *EXPORT DATA PRODUK*\n\n"
    export_text += f"Tanggal Export: {today.strftime('%d %B %Y')}\n"
    export_text += f"Total Produk: {len(produk_list)}\n"
    export_text += "="*40 + "\n\n"
    
    for i, p in enumerate(produk_list, 1):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        selisih = (expired_date - today).days
        
        export_text += f"{i}. {p['nama']}\n"
        export_text += f"   Expired: {expired_date.strftime('%d %B %Y')}\n"
        export_text += f"   Sisa: {selisih} hari\n"
        export_text += f"   Kategori: {p['kategori']}\n"
        export_text += f"   Lokasi: {p['lokasi_detail']}\n"
        export_text += f"   Ditambahkan: {p.get('ditambahkan_tanggal', '-')}\n\n"
        export_text += "-"*30 + "\n\n"
    
    # Kirim sebagai file teks
    with open(f"export_{user_id}.txt", 'w', encoding='utf-8') as f:
        f.write(export_text)
    
    await query.edit_message_text(
        "📊 *EXPORT DATA*\n\n"
        "Data berhasil diexport!",
        parse_mode=ParseMode.MARKDOWN
    )
    
    with open(f"export_{user_id}.txt", 'rb') as f:
        await context.bot.send_document(
            chat_id=user_id,
            document=f,
            filename=f"produk_export_{today.strftime('%Y%m%d')}.txt",
            caption="📊 Data produk lengkap"
        )
    
    os.remove(f"export_{user_id}.txt")
    
    # Tombol kembali
    keyboard = [[InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== NOTIFIKASI OTOMATIS (DENGAN REMINDER CUSTOM) =====================
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
                
                # REMINDER CUSTOM
                custom_reminders = produk.get('reminders', [])
                for remind_hari in custom_reminders:
                    if selisih == remind_hari and notifikasi_terkirim.get(f"{produk_id}_custom_{remind_hari}") != remind_hari:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=(
                                f"🔔 *REMINDER CUSTOM H-{remind_hari}!*\n\n"
                                f"📦 *Produk:* {produk['nama']}\n"
                                f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                                f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                                f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                                f"⏰ *Tersisa {remind_hari} hari lagi!*\n"
                                f"🔔 Ini adalah reminder custom Anda!"
                            ),
                            parse_mode=ParseMode.MARKDOWN
                        )
                        notifikasi_baru[f"{produk_id}_custom_{remind_hari}"] = remind_hari
                
                # NOTIFIKASI STANDAR H-7
                if selisih == 7 and notifikasi_terkirim.get(produk_id) != 7:
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
                
                # NOTIFIKASI STANDAR H-3
                elif selisih == 3 and notifikasi_terkirim.get(produk_id) != 3:
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
                
                # NOTIFIKASI STANDAR H-1
                elif selisih == 1 and notifikasi_terkirim.get(produk_id) != 1:
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
                
                # NOTIFIKASI EXPIRED HARI INI
                elif selisih == 0 and notifikasi_terkirim.get(produk_id) != "expired_hari_ini":
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
                
                # NOTIFIKASI SUDAH EXPIRED
                elif selisih < 0 and notifikasi_terkirim.get(produk_id) != "expired":
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

# ===================== MENU UTAMA (DENGAN FITUR BARU) =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu utama dengan tombol interaktif - VERSI FINAL"""
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="menu_tambah")],
        [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="menu_list")],
        [InlineKeyboardButton("✏️ EDIT PRODUK", callback_data="menu_edit")],
        [InlineKeyboardButton("🔍 CARI PRODUK", callback_data="menu_cari")],
        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="menu_hapus")],
        [InlineKeyboardButton("📊 STATISTIK", callback_data="menu_stats")],
        [InlineKeyboardButton("📍 CEK LOKASI", callback_data="menu_lokasi")],
        [InlineKeyboardButton("⏰ REMINDER", callback_data="menu_reminder")],
        [InlineKeyboardButton("📤 EXPORT DATA", callback_data="menu_export")],
        [InlineKeyboardButton("❓ BANTUAN", callback_data="menu_bantuan")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏪 *MONITORING EXPIRED PRO V4 - FINAL* 🏪\n\n"
        "✨ *FITUR LENGKAP:*\n"
        "✅ Tambah produk dengan lokasi bertingkat\n"
        "✅ Edit produk yang sudah ada\n"
        "✅ Cari produk berdasarkan nama\n"
        "✅ Reminder custom (pilih H-berapa)\n"
        "✅ Export data ke file\n"
        "✅ Statistik lengkap\n"
        "✅ Notifikasi otomatis\n\n"
        "Pilih menu di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

# ===================== CALLBACK HANDLER UTAMA (DENGAN FITUR BARU) =====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua tombol callback - VERSI FINAL"""
    query = update.callback_query
    await query.answer()
    
    # Menu utama
    if query.data == "menu_tambah":
        await query.edit_message_text(
            "📦 *TAMBAH PRODUK BARU*\n\n"
            "Silakan masukkan *nama produk*:",
            parse_mode=ParseMode.MARKDOWN
        )
        return NAMA
    
    elif query.data == "menu_list":
        await list_produk_callback(update, context)
    
    elif query.data == "menu_edit":
        await edit_produk(update, context)
    
    elif query.data == "menu_cari":
        await cari_produk(update, context)
    
    elif query.data == "menu_hapus":
        await hapus_mulai_callback(update, context)
    
    elif query.data == "menu_stats":
        await statistik_callback(update, context)
    
    elif query.data == "menu_lokasi":
        await cek_lokasi_callback(update, context)
    
    elif query.data == "menu_reminder":
        await set_reminder(update, context)
    
    elif query.data == "menu_export":
        await export_data(update, context)
    
    elif query.data == "menu_bantuan":
        await bantuan_callback(update, context)
    
    # Tombol kembali ke menu
    elif query.data == "kembali_ke_menu":
        keyboard = [
            [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="menu_tambah")],
            [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="menu_list")],
            [InlineKeyboardButton("✏️ EDIT PRODUK", callback_data="menu_edit")],
            [InlineKeyboardButton("🔍 CARI PRODUK", callback_data="menu_cari")],
            [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="menu_hapus")],
            [InlineKeyboardButton("📊 STATISTIK", callback_data="menu_stats")],
            [InlineKeyboardButton("📍 CEK LOKASI", callback_data="menu_lokasi")],
            [InlineKeyboardButton("⏰ REMINDER", callback_data="menu_reminder")],
            [InlineKeyboardButton("📤 EXPORT DATA", callback_data="menu_export")],
            [InlineKeyboardButton("❓ BANTUAN", callback_data="menu_bantuan")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🏪 *MONITORING EXPIRED PRO V4 - FINAL* 🏪\n\n"
            "Pilih menu di bawah:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Tombol untuk edit produk
    elif query.data.startswith("edit_"):
        if query.data.startswith("edit_nama_"):
            await edit_nama(update, context)
        elif query.data.startswith("edit_tanggal_"):
            await edit_tanggal(update, context)
        elif query.data.startswith("edit_lokasi_"):
            await edit_lokasi(update, context)
        elif query.data.startswith("edit_kategori_"):
            await edit_kategori(update, context)
        elif query.data.startswith("edit_tipe_"):
            # Untuk edit lokasi - pilih tipe
            if query.data == "edit_tipe_plugin":
                # Pilih nomor plug-in
                keyboard = [
                    [InlineKeyboardButton("📦 Plug-in 1", callback_data="edit_plugin_1")],
                    [InlineKeyboardButton("📦 Plug-in 2", callback_data="edit_plugin_2")],
                    [InlineKeyboardButton("📦 Plug-in 3", callback_data="edit_plugin_3")],
                    [InlineKeyboardButton("📦 Plug-in 4", callback_data="edit_plugin_4")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="menu_edit")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "📍 *PILIH NOMOR PLUG-IN BARU*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            elif query.data == "edit_tipe_showcase":
                keyboard = [
                    [InlineKeyboardButton("🪟 Showcase 1", callback_data="edit_showcase_1")],
                    [InlineKeyboardButton("🪟 Showcase 2", callback_data="edit_showcase_2")],
                    [InlineKeyboardButton("🪟 Showcase 3", callback_data="edit_showcase_3")],
                    [InlineKeyboardButton("🪟 Showcase 4", callback_data="edit_showcase_4")],
                    [InlineKeyboardButton("🔙 KEMBALI", callback_data="menu_edit")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "📍 *PILIH NOMOR SHOWCASE BARU*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
        elif query.data.startswith("edit_plugin_"):
            nomor = query.data.replace("edit_plugin_", "")
            context.user_data['lokasi_tipe'] = "Plug-in"
            context.user_data['lokasi_nomor'] = nomor
            context.user_data['lokasi_detail'] = f"Plug-in {nomor}"
            await simpan_edit(update, context)
        elif query.data.startswith("edit_showcase_"):
            nomor = query.data.replace("edit_showcase_", "")
            context.user_data['lokasi_tipe'] = "Showcase"
            context.user_data['lokasi_nomor'] = nomor
            context.user_data['lokasi_detail'] = f"Showcase {nomor}"
            await simpan_edit(update, context)
        elif query.data.startswith("edit_kategori_"):
            kategori_map = {
                "edit_kategori_susu": "🥛 Susu",
                "edit_kategori_daging": "🥩 Daging",
                "edit_kategori_sayur": "🥦 Sayur",
                "edit_kategori_roti": "🍞 Roti",
                "edit_kategori_minuman": "🧃 Minuman",
                "edit_kategori_lain": "📦 Lainnya"
            }
            context.user_data['kategori_edit'] = kategori_map.get(query.data, "📦 Lainnya")
            await simpan_edit(update, context)
        else:
            # Untuk memilih produk yang akan diedit
            await edit_produk_pilih(update, context)
    
    # Tombol untuk reminder
    elif query.data.startswith("reminder_"):
        if query.data.startswith("remind_"):
            await simpan_reminder(update, context)
        else:
            await pilih_reminder(update, context)
    
    # Tombol untuk tipe lokasi (tambah produk)
    elif query.data == "tipe_plugin":
        keyboard = [
            [InlineKeyboardButton("📦 Plug-in 1", callback_data="plugin_1")],
            [InlineKeyboardButton("📦 Plug-in 2", callback_data="plugin_2")],
            [InlineKeyboardButton("📦 Plug-in 3", callback_data="plugin_3")],
            [InlineKeyboardButton("📦 Plug-in 4", callback_data="plugin_4")],
            [InlineKeyboardButton("🔙 KEMBALI", callback_data="kembali_tipe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH NOMOR PLUG-IN:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif query.data == "tipe_showcase":
        keyboard = [
            [InlineKeyboardButton("🪟 Showcase 1", callback_data="showcase_1")],
            [InlineKeyboardButton("🪟 Showcase 2", callback_data="showcase_2")],
            [InlineKeyboardButton("🪟 Showcase 3", callback_data="showcase_3")],
            [InlineKeyboardButton("🪟 Showcase 4", callback_data="showcase_4")],
            [InlineKeyboardButton("🔙 KEMBALI", callback_data="kembali_tipe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH NOMOR SHOWCASE:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif query.data == "kembali_tipe":
        keyboard = [
            [InlineKeyboardButton("📦 PLUG-IN (Rak)", callback_data="tipe_plugin")],
            [InlineKeyboardButton("🪟 SHOWCASE (Etalase)", callback_data="tipe_showcase")],
            [InlineKeyboardButton("🔙 BATAL", callback_data="kembali_ke_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH TIPE LOKASI:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Pilih nomor plug-in (tambah produk)
    elif query.data.startswith("plugin_"):
        nomor = query.data.replace("plugin_", "")
        context.user_data['lokasi_tipe'] = "Plug-in"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Plug-in {nomor}"
        await pilih_kategori_callback(update, context)
    
    # Pilih nomor showcase (tambah produk)
    elif query.data.startswith("showcase_"):
        nomor = query.data.replace("showcase_", "")
        context.user_data['lokasi_tipe'] = "Showcase"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Showcase {nomor}"
        await pilih_kategori_callback(update, context)
    
    # Pilih kategori (tambah produk)
    elif query.data.startswith("kategori_"):
        kategori_map = {
            "kategori_susu": "🥛 Susu",
            "kategori_daging": "🥩 Daging",
            "kategori_sayur": "🥦 Sayur",
            "kategori_roti": "🍞 Roti",
            "kategori_minuman": "🧃 Minuman",
            "kategori_lain": "📦 Lainnya"
        }
        context.user_data['kategori'] = kategori_map.get(query.data, "📦 Lainnya")
        await simpan_produk_callback(update, context)
    
    # Hapus produk
    elif query.data.startswith("hapus_"):
        await hapus_produk_callback(update, context)
    
    elif query.data == "batal_hapus":
        await query.edit_message_text("🚫 Penghapusan dibatalkan.")
        # Kembali ke menu
        keyboard = [[InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# [Sisanya sama dengan kode sebelumnya untuk fungsi-fungsi yang sudah ada]
# (list_produk_callback, statistik_callback, cek_lokasi_callback, bantuan_callback,
#  hapus_mulai_callback, hapus_produk_callback, pilih_kategori_callback, 
#  simpan_produk_callback, nama_produk, tanggal_produk, dll.)

# ===================== MAIN =====================
def main():
    print("="*60)
    print("🏪 BOT EXPIRED PRO V4 - VERSI FINAL DENGAN 10 FITUR!")
    print("="*60)
    print("✅ FITUR 1: Tambah Produk + Lokasi Bertingkat")
    print("✅ FITUR 2: Lihat Semua Produk")
    print("✅ FITUR 3: Edit Produk (Nama, Tanggal, Lokasi, Kategori)")
    print("✅ FITUR 4: Cari Produk Berdasarkan Nama")
    print("✅ FITUR 5: Hapus Produk")
    print("✅ FITUR 6: Statistik Lengkap")
    print("✅ FITUR 7: Cek Produk per Lokasi")
    print("✅ FITUR 8: Reminder Custom (Pilih H-berapa)")
    print("✅ FITUR 9: Export Data ke File")
    print("✅ FITUR 10: Notifikasi Otomatis (H-7, H-3, H-1, Expired)")
    print("="*60)
    print(f"🤖 Token: {TOKEN[:15]}...")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Job queue untuk notifikasi otomatis
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(cek_expired, interval=21600, first=10)
        print("⏰ Notifikasi otomatis: AKTIF (cek setiap 6 jam)")
    
    # Conversation handler untuk TAMBAH produk
    tambah_conv = ConversationHandler(
        entry_points=[CommandHandler('tambah', tambah_mulai)],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_produk)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_produk)],
            TIPE_LOKASI: [CallbackQueryHandler(button_callback, pattern="^(tipe_plugin|tipe_showcase|kembali_ke_menu)$")],
            PLUGIN: [CallbackQueryHandler(button_callback, pattern="^(plugin_|showcase_|kembali_tipe|kembali_ke_menu)$")],
            SHOWCASE: [CallbackQueryHandler(button_callback, pattern="^(plugin_|showcase_|kembali_tipe|kembali_ke_menu)$")],
            KATEGORI: [CallbackQueryHandler(button_callback, pattern="^(kategori_|kembali_tipe|kembali_ke_menu)$")],
        },
        fallbacks=[CommandHandler('batal', lambda u,c: ConversationHandler.END)]
    )
    
    # Conversation handler untuk CARI produk
    cari_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cari_produk, pattern="^menu_cari$")],
        states={99: [MessageHandler(filters.TEXT & ~filters.COMMAND, proses_cari)]},
        fallbacks=[CommandHandler('batal', lambda u,c: ConversationHandler.END)]
    )
    
    # Conversation handler untuk EDIT produk
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_produk, pattern="^menu_edit$")],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, simpan_edit)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, simpan_edit)],
            TIPE_LOKASI: [CallbackQueryHandler(button_callback, pattern="^edit_tipe_")],
            PLUGIN: [CallbackQueryHandler(button_callback, pattern="^edit_plugin_")],
            SHOWCASE: [CallbackQueryHandler(button_callback, pattern="^edit_showcase_")],
            KATEGORI: [CallbackQueryHandler(button_callback, pattern="^edit_kategori_")],
        },
        fallbacks=[CommandHandler('batal', lambda u,c: ConversationHandler.END)]
    )
    
    # Daftarkan semua handler
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('list', list_produk_callback_wrapper))
    app.add_handler(CommandHandler('stats', statistik_callback_wrapper))
    app.add_handler(CommandHandler('lokasi', cek_lokasi_callback_wrapper))
    app.add_handler(CommandHandler('bantuan', bantuan_callback_wrapper))
    app.add_handler(tambah_conv)
    app.add_handler(cari_conv)
    app.add_handler(edit_conv)
    
    # Callback query handler (untuk semua tombol)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ BOT SIAP! Menjalankan polling...")
    print("📱 Cek Telegram Anda sekarang!")
    print("="*60)
    
    app.run_polling()

# [Semua wrapper functions dan fungsi lainnya tetap sama]

if __name__ == "__main__":
    main()
