import os
import json
import csv
import io
import calendar
from datetime import datetime, timedelta, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler,
    JobQueue
)
from telegram.constants import ParseMode
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

# ===================== KONFIGURASI =====================
TOKEN = "8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw"
DATA_FILE = "produk_database.json"
REKAP_FILE = "rekap_harian.json"

# States untuk ConversationHandler
NAMA, TANGGAL, FOTO, TIPE_LOKASI, PLUGIN, SHOWCASE, KATEGORI = range(7)

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
    return data.get(str(user_id), {"produk": [], "notifikasi": {}, "rekap": []})

def save_user_data(user_id, user_data):
    """Save data spesifik user"""
    data = load_data()
    data[str(user_id)] = user_data
    save_data(data)

# ===================== REKAP HARIAN =====================
def load_rekap():
    """Load data rekap harian"""
    if os.path.exists(REKAP_FILE):
        try:
            with open(REKAP_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_rekap(data):
    """Save data rekap harian"""
    with open(REKAP_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user_rekap(user_id):
    """Get rekap spesifik user"""
    data = load_rekap()
    return data.get(str(user_id), {"cek_harian": []})

def save_user_rekap(user_id, rekap_data):
    """Save rekap spesifik user"""
    data = load_rekap()
    data[str(user_id)] = rekap_data
    save_rekap(data)

# ===================== FITUR 3: REKAP CEK HARIAN =====================
async def tambah_rekap_cek(user_id, lokasi):
    """Tambah rekap pengecekan harian"""
    rekap_data = get_user_rekap(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now().strftime('%H:%M:%S')
    
    # Cari apakah sudah ada rekap hari ini
    found = False
    for item in rekap_data["cek_harian"]:
        if item["tanggal"] == today:
            if lokasi not in item["lokasi_dicek"]:
                item["lokasi_dicek"].append(lokasi)
                item["waktu_cek"].append(now)
                item["jumlah_cek"] += 1
            found = True
            break
    
    if not found:
        rekap_data["cek_harian"].append({
            "tanggal": today,
            "lokasi_dicek": [lokasi],
            "waktu_cek": [now],
            "jumlah_cek": 1
        })
    
    save_user_rekap(user_id, rekap_data)

async def rekap_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lihat rekap pengecekan hari ini"""
    user_id = update.effective_user.id
    rekap_data = get_user_rekap(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Cari rekap hari ini
    rekap_today = None
    for item in rekap_data["cek_harian"]:
        if item["tanggal"] == today:
            rekap_today = item
            break
    
    if not rekap_today:
        await update.message.reply_text(
            "📋 *REKAP CEK HARI INI*\n\n"
            "Belum ada pengecekan hari ini.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    pesan = f"📋 *REKAP CEK HARI INI - {today}*\n\n"
    pesan += f"Total pengecekan: {rekap_today['jumlah_cek']}x\n\n"
    pesan += "*Lokasi yang sudah dicek:*\n"
    
    for i, (lokasi, waktu) in enumerate(zip(rekap_today['lokasi_dicek'], rekap_today['waktu_cek']), 1):
        pesan += f"{i}. 📍 {lokasi} - ⏰ {waktu}\n"
    
    await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)

# ===================== FITUR 1: PICKER TANGGAL OTOMATIS =====================
def buat_kalender(tahun=None, bulan=None):
    """Buat tampilan kalender untuk memilih tanggal"""
    if tahun is None:
        tahun = datetime.now().year
    if bulan is None:
        bulan = datetime.now().month
    
    # Buat header bulan
    nama_bulan = calendar.month_name[bulan]
    header = f"{nama_bulan} {tahun}"
    
    # Buat keyboard kalender
    keyboard = []
    
    # Tombol navigasi bulan
    nav_row = []
    prev_month = bulan - 1
    prev_year = tahun
    next_month = bulan + 1
    next_year = tahun
    
    if prev_month < 1:
        prev_month = 12
        prev_year = tahun - 1
    if next_month > 12:
        next_month = 1
        next_year = tahun + 1
    
    nav_row.append(InlineKeyboardButton("◀️", callback_data=f"cal_prev_{prev_year}_{prev_month}"))
    nav_row.append(InlineKeyboardButton(f"{header}", callback_data="cal_current"))
    nav_row.append(InlineKeyboardButton("▶️", callback_data=f"cal_next_{next_year}_{next_month}"))
    keyboard.append(nav_row)
    
    # Hari dalam seminggu
    hari_row = []
    for hari in ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]:
        hari_row.append(InlineKeyboardButton(hari, callback_data="noop"))
    keyboard.append(hari_row)
    
    # Tanggal dalam bulan
    cal = calendar.monthcalendar(tahun, bulan)
    today = datetime.now().day
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    for week in cal:
        week_row = []
        for day in week:
            if day == 0:
                week_row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                # Tandai tanggal hari ini
                if day == today and bulan == current_month and tahun == current_year:
                    text = f"•{day}•"
                else:
                    text = str(day)
                
                week_row.append(InlineKeyboardButton(
                    text, 
                    callback_data=f"cal_date_{tahun}_{bulan}_{day}"
                ))
        keyboard.append(week_row)
    
    # Tombol aksi
    action_row = [
        InlineKeyboardButton("✅ Hari Ini", callback_data="cal_today"),
        InlineKeyboardButton("❌ Batal", callback_data="cal_cancel")
    ]
    keyboard.append(action_row)
    
    return keyboard

async def tanggal_mulai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan kalender untuk memilih tanggal"""
    keyboard = buat_kalender()
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📅 *PILIH TANGGAL EXPIRED*\n\n"
        "Klik tanggal pada kalender di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return TANGGAL

async def tanggal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pilihan tanggal dari kalender"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "cal_cancel":
        await query.edit_message_text("❌ Pembatalan tanggal.")
        return ConversationHandler.END
    
    elif data == "cal_today":
        today = datetime.now()
        tanggal_str = today.strftime('%Y-%m-%d')
        context.user_data['tanggal'] = tanggal_str
        await query.edit_message_text(
            f"✅ Tanggal dipilih: *{today.strftime('%d %B %Y')}*",
            parse_mode=ParseMode.MARKDOWN
        )
        # LANJUT KE FOTO (FITUR 2)
        await query.message.reply_text(
            "📸 *UPLOAD FOTO PRODUK*\n\n"
            "Silakan kirim foto produk (atau ketik /skip jika tidak ada foto):",
            parse_mode=ParseMode.MARKDOWN
        )
        return FOTO
    
    elif data.startswith("cal_date_"):
        _, _, tahun, bulan, hari = data.split('_')
        tanggal = date(int(tahun), int(bulan), int(hari))
        tanggal_str = tanggal.strftime('%Y-%m-%d')
        context.user_data['tanggal'] = tanggal_str
        await query.edit_message_text(
            f"✅ Tanggal dipilih: *{tanggal.strftime('%d %B %Y')}*",
            parse_mode=ParseMode.MARKDOWN
        )
        # LANJUT KE FOTO (FITUR 2)
        await query.message.reply_text(
            "📸 *UPLOAD FOTO PRODUK*\n\n"
            "Silakan kirim foto produk (atau ketik /skip jika tidak ada foto):",
            parse_mode=ParseMode.MARKDOWN
        )
        return FOTO
    
    elif data.startswith("cal_prev_"):
        _, _, tahun, bulan = data.split('_')
        keyboard = buat_kalender(int(tahun), int(bulan))
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📅 *PILIH TANGGAL EXPIRED*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return TANGGAL
    
    elif data.startswith("cal_next_"):
        _, _, tahun, bulan = data.split('_')
        keyboard = buat_kalender(int(tahun), int(bulan))
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📅 *PILIH TANGGAL EXPIRED*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return TANGGAL

# ===================== FITUR 2: FOTO PRODUK =====================
async def foto_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima foto produk"""
    # Cek apakah ada foto
    if update.message.photo:
        # Ambil foto dengan kualitas terbaik (terakhir dalam array)
        foto = update.message.photo[-1]
        file_id = foto.file_id
        
        # Simpan file_id foto
        context.user_data['foto_id'] = file_id
        
        await update.message.reply_text("✅ Foto berhasil diterima!")
    else:
        context.user_data['foto_id'] = None
        await update.message.reply_text("⏭️ Melewati foto produk.")
    
    # LANJUT KE PILIH LOKASI
    keyboard = [
        [InlineKeyboardButton("📦 PLUG-IN (Rak)", callback_data="tipe_plugin")],
        [InlineKeyboardButton("🪟 SHOWCASE (Etalase)", callback_data="tipe_showcase")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📍 *PILIH TIPE LOKASI:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return TIPE_LOKASI

async def skip_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip upload foto"""
    context.user_data['foto_id'] = None
    await update.message.reply_text("⏭️ Melewati foto produk.")
    
    # LANJUT KE PILIH LOKASI
    keyboard = [
        [InlineKeyboardButton("📦 PLUG-IN (Rak)", callback_data="tipe_plugin")],
        [InlineKeyboardButton("🪟 SHOWCASE (Etalase)", callback_data="tipe_showcase")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📍 *PILIH TIPE LOKASI:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return TIPE_LOKASI

# ===================== LOKASI BERTINGKAT =====================
async def tipe_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih tipe lokasi"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "tipe_plugin":
        keyboard = [
            [InlineKeyboardButton("📦 Plug-in 1", callback_data="plugin_1")],
            [InlineKeyboardButton("📦 Plug-in 2", callback_data="plugin_2")],
            [InlineKeyboardButton("📦 Plug-in 3", callback_data="plugin_3")],
            [InlineKeyboardButton("📦 Plug-in 4", callback_data="plugin_4")]
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
            [InlineKeyboardButton("🪟 Showcase 4", callback_data="showcase_4")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH NOMOR SHOWCASE:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    return PLUGIN

async def pilih_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih kategori produk"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("plugin_"):
        nomor = query.data.replace("plugin_", "")
        context.user_data['lokasi_tipe'] = "Plug-in"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Plug-in {nomor}"
    elif query.data.startswith("showcase_"):
        nomor = query.data.replace("showcase_", "")
        context.user_data['lokasi_tipe'] = "Showcase"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Showcase {nomor}"
    
    # TAMBAH REKAP CEK (FITUR 3)
    user_id = update.effective_user.id
    await tambah_rekap_cek(user_id, context.user_data['lokasi_detail'])
    
    keyboard = [
        [InlineKeyboardButton("🥛 Susu", callback_data="kategori_susu")],
        [InlineKeyboardButton("🥩 Daging", callback_data="kategori_daging")],
        [InlineKeyboardButton("🥦 Sayur", callback_data="kategori_sayur")],
        [InlineKeyboardButton("🍞 Roti", callback_data="kategori_roti")],
        [InlineKeyboardButton("🧃 Minuman", callback_data="kategori_minuman")],
        [InlineKeyboardButton("📦 Lainnya", callback_data="kategori_lain")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📍 *Lokasi:* {context.user_data['lokasi_detail']}\n\n"
        f"🏷 *PILIH KATEGORI PRODUK:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return KATEGORI

async def simpan_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan produk ke database"""
    query = update.callback_query
    await query.answer()
    
    kategori_map = {
        "kategori_susu": "🥛 Susu",
        "kategori_daging": "🥩 Daging",
        "kategori_sayur": "🥦 Sayur",
        "kategori_roti": "🍞 Roti",
        "kategori_minuman": "🧃 Minuman",
        "kategori_lain": "📦 Lainnya"
    }
    
    kategori = kategori_map.get(query.data, "📦 Lainnya")
    context.user_data['kategori'] = kategori
    
    user_id = update.effective_user.id
    
    produk = {
        "nama": context.user_data['nama'],
        "tanggal": context.user_data['tanggal'],
        "lokasi_tipe": context.user_data['lokasi_tipe'],
        "lokasi_nomor": context.user_data['lokasi_nomor'],
        "lokasi_detail": context.user_data['lokasi_detail'],
        "kategori": kategori,
        "foto_id": context.user_data.get('foto_id'),
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
    
    pesan = f"✅ *PRODUK BERHASIL DITAMBAH!*\n\n"
    pesan += f"📦 *Nama:* {produk['nama']}\n"
    pesan += f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
    pesan += f"📊 *Status:* {status}\n"
    pesan += f"🏷 *Kategori:* {produk['kategori']}\n"
    pesan += f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
    pesan += f"⏰ *Ditambahkan:* {produk['ditambahkan_jam']} - {produk['ditambahkan_tanggal']}\n"
    
    if produk.get('foto_id'):
        pesan += f"📸 *Foto:* Ada\n"
        # Kirim foto jika ada
        await context.bot.send_photo(
            chat_id=user_id,
            photo=produk['foto_id'],
            caption=f"Foto {produk['nama']}"
        )
    
    await query.edit_message_text(pesan, parse_mode=ParseMode.MARKDOWN)
    
    # Tampilkan menu
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH LAGI", callback_data="tambah")],
        [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="list")],
        [InlineKeyboardButton("📊 EXPORT EXCEL", callback_data="export")],
        [InlineKeyboardButton("🏠 MENU UTAMA", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "Pilih aksi selanjutnya:",
        reply_markup=reply_markup
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ===================== FITUR 4: EXPORT KE EXCEL =====================
async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export data ke Excel dengan pilihan periode"""
    keyboard = [
        [InlineKeyboardButton("📊 REKAP HARIAN", callback_data="export_harian")],
        [InlineKeyboardButton("📅 REKAP MINGGUAN", callback_data="export_mingguan")],
        [InlineKeyboardButton("🗓️ REKAP BULANAN", callback_data="export_bulanan")],
        [InlineKeyboardButton("📈 SEMUA DATA", callback_data="export_semua")],
        [InlineKeyboardButton("❌ BATAL", callback_data="export_batal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *EXPORT DATA KE EXCEL*\n\n"
        "Pilih periode yang ingin diexport:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pilihan export"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "export_batal":
        await query.edit_message_text("❌ Export dibatalkan.")
        return
    
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await query.edit_message_text("📭 Tidak ada data untuk diexport.")
        return
    
    # Filter berdasarkan periode
    today = datetime.now().date()
    filtered_produk = []
    judul = ""
    
    if query.data == "export_harian":
        judul = f"REKAP HARIAN - {today.strftime('%d-%m-%Y')}"
        for p in produk_list:
            tgl_tambah = datetime.strptime(p['ditambahkan_tanggal'], '%d/%m/%Y').date()
            if tgl_tambah == today:
                filtered_produk.append(p)
    
    elif query.data == "export_mingguan":
        judul = f"REKAP MINGGUAN - {today.strftime('WEEK %W %Y')}"
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        for p in produk_list:
            tgl_tambah = datetime.strptime(p['ditambahkan_tanggal'], '%d/%m/%Y').date()
            if start_week <= tgl_tambah <= end_week:
                filtered_produk.append(p)
    
    elif query.data == "export_bulanan":
        judul = f"REKAP BULANAN - {today.strftime('%B %Y')}"
        for p in produk_list:
            tgl_tambah = datetime.strptime(p['ditambahkan_tanggal'], '%d/%m/%Y').date()
            if tgl_tambah.month == today.month and tgl_tambah.year == today.year:
                filtered_produk.append(p)
    
    elif query.data == "export_semua":
        judul = "SEMUA DATA PRODUK"
        filtered_produk = produk_list
    
    if not filtered_produk:
        await query.edit_message_text(f"📭 Tidak ada data untuk periode ini.")
        return
    
    # Buat file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Produk Expired"
    
    # Header
    headers = ["No", "Nama Produk", "Tanggal Expired", "Sisa Hari", "Status", 
               "Kategori", "Lokasi", "Tipe Lokasi", "Nomor", "Waktu Tambah", "Tanggal Tambah"]
    
    # Style header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4CAF50", end_color="4CAF50", fill_type="solid")
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    
    # Isi data
    today = datetime.now().date()
    for row, p in enumerate(filtered_produk, 2):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        selisih = (expired_date - today).days
        
        if selisih < 0:
            status = "EXPIRED"
            status_color = "FF4444"
        elif selisih == 0:
            status = "EXPIRED HARI INI"
            status_color = "FFA500"
        elif selisih <= 3:
            status = f"WARNING H-{selisih}"
            status_color = "FFA500"
        elif selisih <= 7:
            status = f"WARNING H-{selisih}"
            status_color = "FFEE44"
        else:
            status = f"AMAN ({selisih} hari)"
            status_color = "4CAF50"
        
        data = [
            row-1,
            p['nama'],
            expired_date.strftime('%d/%m/%Y'),
            selisih,
            status,
            p['kategori'],
            p['lokasi_detail'],
            p['lokasi_tipe'],
            p['lokasi_nomor'],
            p.get('ditambahkan_jam', '-'),
            p.get('ditambahkan_tanggal', '-')
        ]
        
        for col, value in enumerate(data, 1):
            cell = ws.cell(row=row, column=col, value=value)
            if col == 5:  # Kolom status
                cell.fill = PatternFill(start_color=status_color, end_color=status_color, fill_type="solid")
    
    # Auto adjust column width
    for col in range(1, len(headers)+1):
        ws.column_dimensions[chr(64+col)].width = 15
    
    # Save ke memory
    excel_file = io.BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)
    
    # Kirim file
    await query.edit_message_text(f"📊 *MEMPROSES EXPORT...*\n\n{judul}", parse_mode=ParseMode.MARKDOWN)
    
    await context.bot.send_document(
        chat_id=user_id,
        document=excel_file,
        filename=f"rekap_produk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        caption=f"📊 {judul}\nTotal: {len(filtered_produk)} produk"
    )

# ===================== NOTIFIKASI OTOMATIS =====================
async def cek_expired(context: ContextTypes.DEFAULT_TYPE):
    """Cek produk expired dan kirim notifikasi"""
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
                
                if selisih == 7 and notifikasi_terkirim.get(produk_id) != 7:
                    await kirim_notifikasi(context, user_id_str, produk, expired_date, selisih, "H-7")
                    notifikasi_baru[produk_id] = 7
                
                elif selisih == 3 and notifikasi_terkirim.get(produk_id) != 3:
                    await kirim_notifikasi(context, user_id_str, produk, expired_date, selisih, "H-3")
                    notifikasi_baru[produk_id] = 3
                
                elif selisih == 1 and notifikasi_terkirim.get(produk_id) != 1:
                    await kirim_notifikasi(context, user_id_str, produk, expired_date, selisih, "H-1")
                    notifikasi_baru[produk_id] = 1
                
                elif selisih == 0 and notifikasi_terkirim.get(produk_id) != "expired_hari_ini":
                    await kirim_notifikasi(context, user_id_str, produk, expired_date, selisih, "EXPIRED HARI INI")
                    notifikasi_baru[produk_id] = "expired_hari_ini"
                
                elif selisih < 0 and notifikasi_terkirim.get(produk_id) != "expired":
                    await kirim_notifikasi(context, user_id_str, produk, expired_date, selisih, f"SUDAH EXPIRED {abs(selisih)} HARI")
                    notifikasi_baru[produk_id] = "expired"
                
                else:
                    if produk_id in notifikasi_terkirim:
                        notifikasi_baru[produk_id] = notifikasi_terkirim[produk_id]
                        
            except Exception as e:
                print(f"Error notifikasi: {e}")
        
        user_data["notifikasi"] = notifikasi_baru
        save_user_data(user_id_str, user_data)

async def kirim_notifikasi(context, user_id, produk, expired_date, selisih, status):
    """Kirim notifikasi ke user"""
    icon = "⚠️" if "H-" in status else "❌"
    
    pesan = f"{icon} *{status}*\n\n"
    pesan += f"📦 *Produk:* {produk['nama']}\n"
    pesan += f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
    pesan += f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
    pesan += f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
    
    if selisih > 0:
        pesan += f"⏰ *Tersisa {selisih} hari lagi!*\n"
    else:
        pesan += f"⚠️ *Produk sudah tidak layak!*\n"
    
    pesan += "🔔 Segera tindak lanjuti!"
    
    await context.bot.send_message(
        chat_id=int(user_id),
        text=pesan,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Kirim foto jika ada
    if produk.get('foto_id'):
        await context.bot.send_photo(
            chat_id=int(user_id),
            photo=produk['foto_id'],
            caption=f"Foto {produk['nama']}"
        )

# ===================== MENU UTAMA =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu utama dengan tombol interaktif"""
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="tambah")],
        [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="list")],
        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="hapus")],
        [InlineKeyboardButton("📊 STATISTIK", callback_data="stats")],
        [InlineKeyboardButton("📍 REKAP CEK", callback_data="rekap")],
        [InlineKeyboardButton("📈 EXPORT EXCEL", callback_data="export_menu")],
        [InlineKeyboardButton("❓ BANTUAN", callback_data="bantuan")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏪 *MONITORING EXPIRED PRO V4* 🏪\n\n"
        "✨ *FITUR BARU:*\n"
        "✅ Pilih tanggal dengan kalender\n"
        "✅ Upload foto produk\n"
        "✅ Rekap pengecekan harian\n"
        "✅ Export ke Excel (harian/mingguan/bulanan)\n\n"
        "Pilih menu di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "tambah":
        await query.edit_message_text(
            "📦 *TAMBAH PRODUK BARU*\n\nSilakan masukkan *nama produk*:",
            parse_mode=ParseMode.MARKDOWN
        )
        return NAMA
    
    elif query.data == "list":
        await list_produk(update, context)
    
    elif query.data == "stats":
        await statistik(update, context)
    
    elif query.data == "rekap":
        await rekap_harian(update, context)
    
    elif query.data == "export_menu":
        keyboard = [
            [InlineKeyboardButton("📊 REKAP HARIAN", callback_data="export_harian")],
            [InlineKeyboardButton("📅 REKAP MINGGUAN", callback_data="export_mingguan")],
            [InlineKeyboardButton("🗓️ REKAP BULANAN", callback_data="export_bulanan")],
            [InlineKeyboardButton("📈 SEMUA DATA", callback_data="export_semua")],
            [InlineKeyboardButton("🔙 KEMBALI", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📊 *EXPORT DATA KE EXCEL*\n\nPilih periode:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    elif query.data == "bantuan":
        await bantuan(update, context)
    
    elif query.data == "menu":
        await start(update, context)

# ===================== LIST PRODUK =====================
async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan semua produk"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Belum ada produk*",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    produk_list.sort(key=lambda x: x['tanggal'])
    today = datetime.now().date()
    pesan = "📋 *DAFTAR PRODUK*\n\n"
    
    for i, p in enumerate(produk_list, 1):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        selisih = (expired_date - today).days
        
        if selisih < 0:
            icon = "❌"
        elif selisih == 0:
            icon = "⚠️⚠️"
        elif selisih <= 3:
            icon = "⚠️"
        elif selisih <= 7:
            icon = "⚡"
        else:
            icon = "✅"
        
        pesan += f"{i}. {icon} *{p['nama']}*\n"
        pesan += f"   📅 {expired_date.strftime('%d/%m/%Y')} ({selisih} hari)\n"
        pesan += f"   🏷 {p['kategori']}\n"
        pesan += f"   📍 {p['lokasi_detail']}\n"
        if p.get('foto_id'):
            pesan += f"   📸 Ada foto\n"
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
    aman = warning_h7 = warning_h3 = warning_h1 = expired_hari_ini = expired = 0
    kategori = {}
    lokasi_plugin = {f"Plug-in {i}": 0 for i in range(1,5)}
    lokasi_showcase = {f"Showcase {i}": 0 for i in range(1,5)}
    
    for p in produk_list:
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        selisih = (expired_date - today).days
        
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
        
        kat = p.get('kategori', 'Lainnya')
        kategori[kat] = kategori.get(kat, 0) + 1
        
        if p['lokasi_detail'].startswith('Plug-in'):
            lokasi_plugin[p['lokasi_detail']] += 1
        elif p['lokasi_detail'].startswith('Showcase'):
            lokasi_showcase[p['lokasi_detail']] += 1
    
    pesan = "📊 *STATISTIK PRODUK*\n\n"
    pesan += "*STATUS:*\n"
    pesan += f"✅ Aman: {aman}\n"
    pesan += f"⚡ H-7: {warning_h7}\n"
    pesan += f"⚠️ H-3: {warning_h3}\n"
    pesan += f"🔥 H-1: {warning_h1}\n"
    pesan += f"⏰ Expired hari ini: {expired_hari_ini}\n"
    pesan += f"❌ Expired: {expired}\n\n"
    
    pesan += "*KATEGORI:*\n"
    for kat, jml in kategori.items():
        pesan += f"{kat}: {jml}\n"
    pesan += "\n"
    
    pesan += "*LOKASI:*\n"
    for lok, jml in {**lokasi_plugin, **lokasi_showcase}.items():
        if jml > 0:
            pesan += f"📍 {lok}: {jml}\n"
    
    pesan += f"\n📦 *TOTAL: {len(produk_list)}*"
    
    await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)

# ===================== BANTUAN =====================
async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan bantuan"""
    await update.message.reply_text(
        "📚 *BANTUAN PENGGUNAAN V4*\n\n"
        "*FITUR BARU:*\n"
        "1️⃣ *Kalender Interaktif* - Pilih tanggal tanpa ngetik\n"
        "2️⃣ *Foto Produk* - Upload foto setiap produk\n"
        "3️⃣ *Rekap Harian* - Lacak area yang sudah dicek\n"
        "4️⃣ *Export Excel* - Rekap harian/mingguan/bulanan\n\n"
        
        "*PERINTAH:*\n"
        "/start - Menu utama\n"
        "/tambah - Tambah produk\n"
        "/list - Lihat produk\n"
        "/stats - Statistik\n"
        "/rekap - Rekap cek hari ini\n"
        "/export - Export ke Excel\n"
        "/bantuan - Bantuan ini\n\n"
        
        "*LOKASI:* Plug-in 1-4 | Showcase 1-4\n"
        "*NOTIFIKASI:* H-7, H-3, H-1, expired",
        parse_mode=ParseMode.MARKDOWN
    )

# ===================== MAIN =====================
def main():
    print("="*60)
    print("🏪 BOT EXPIRED PRO V4 - DENGAN 4 FITUR BARU!")
    print("="*60)
    print("✅ FITUR 1: Pilih tanggal dengan kalender")
    print("✅ FITUR 2: Upload foto produk")
    print("✅ FITUR 3: Rekap pengecekan harian")
    print("✅ FITUR 4: Export ke Excel (harian/mingguan/bulanan)")
    print("="*60)
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Job queue notifikasi (cek setiap 6 jam)
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(cek_expired, interval=21600, first=10)
        print("⏰ Notifikasi otomatis: AKTIF (cek setiap 6 jam)")
    
    # Conversation handler
    tambah_conv = ConversationHandler(
        entry_points=[
            CommandHandler('tambah', lambda u,c: tanggal_mulai(u,c) if hasattr(u, 'message') else None),
            CallbackQueryHandler(menu_callback, pattern="^tambah$")
        ],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: (setattr(c.user_data, 'nama', u.message.text) or tanggal_mulai(u,c)))],
            TANGGAL: [CallbackQueryHandler(tanggal_callback)],
            FOTO: [
                MessageHandler(filters.PHOTO, foto_produk),
                CommandHandler('skip', skip_foto)
            ],
            TIPE_LOKASI: [CallbackQueryHandler(tipe_lokasi, pattern="^tipe_")],
            PLUGIN: [CallbackQueryHandler(pilih_kategori, pattern="^(plugin_|showcase_)")],
            SHOWCASE: [CallbackQueryHandler(pilih_kategori, pattern="^(plugin_|showcase_)")],
            KATEGORI: [CallbackQueryHandler(simpan_produk, pattern="^kategori_")],
        },
        fallbacks=[CommandHandler('batal', lambda u,c: ConversationHandler.END)]
    )
    
    # Daftarkan handler
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('list', list_produk))
    app.add_handler(CommandHandler('stats', statistik))
    app.add_handler(CommandHandler('rekap', rekap_harian))
    app.add_handler(CommandHandler('export', export_excel))
    app.add_handler(CommandHandler('bantuan', bantuan))
    app.add_handler(tambah_conv)
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(export_callback, pattern="^export_"))
    app.add_handler(CallbackQueryHandler(menu_callback))
    
    print("✅ BOT SIAP! Menjalankan polling...")
    print("📱 Cek Telegram Anda sekarang!")
    print("="*60)
    
    app.run_polling()

if __name__ == "__main__":
    main()
