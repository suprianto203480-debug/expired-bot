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
import csv
import io

# ===================== KONFIGURASI =====================
TOKEN = "8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw"
DATA_FILE = "produk_database.json"

# States untuk ConversationHandler
NAMA, TANGGAL, TIPE_LOKASI, PLUGIN, SHOWCASE, KATEGORI = range(6)

# ===================== FUNGSI WAKTU WIB =====================
def get_waktu_wib():
    """Mendapatkan waktu WIB (UTC+7)"""
    waktu_utc = datetime.utcnow()
    waktu_wib = waktu_utc + timedelta(hours=7)
    return waktu_wib

def format_waktu_wib():
    """Format waktu WIB untuk ditampilkan"""
    waktu = get_waktu_wib()
    return {
        "full": waktu.strftime('%Y-%m-%d %H:%M:%S'),
        "tanggal": waktu.strftime('%d/%m/%Y'),
        "jam": waktu.strftime('%H:%M'),
        "tanggal_lengkap": waktu.strftime('%d %B %Y'),
        "hari": waktu.strftime('%A'),
        "bulan": waktu.strftime('%B'),
        "tahun": waktu.strftime('%Y')
    }

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

# ===================== FUNGSI EXPORT CSV =====================
async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export data produk ke file CSV (tanpa openpyxl)"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Tidak ada data untuk diexport*",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Kirim pesan proses
    waiting_msg = await update.message.reply_text(
        "⏳ *Sedang memproses export data...*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Buat file CSV dalam memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header CSV
        writer.writerow([
            "No", 
            "Nama Produk", 
            "Tanggal Expired", 
            "Sisa Hari", 
            "Status",
            "Kategori", 
            "Lokasi", 
            "Tipe Lokasi", 
            "Nomor",
            "Jam Ditambahkan",
            "Tanggal Ditambahkan"
        ])
        
        # Data
        today = datetime.now().date()
        
        for i, p in enumerate(produk_list, 1):
            expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
            selisih = (expired_date - today).days
            
            # Tentukan status
            if selisih < 0:
                status = f"EXPIRED ({abs(selisih)} hari)"
            elif selisih == 0:
                status = "EXPIRED HARI INI"
            elif selisih == 1:
                status = f"H-{selisih} (BESOK!)"
            elif selisih <= 3:
                status = f"H-{selisih}"
            elif selisih <= 7:
                status = f"H-{selisih}"
            else:
                status = f"AMAN ({selisih} hari)"
            
            writer.writerow([
                i,
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
            ])
        
        # Dapatkan string CSV
        csv_data = output.getvalue()
        output.close()
        
        # Convert ke bytes untuk dikirim
        csv_bytes = io.BytesIO()
        csv_bytes.write(csv_data.encode('utf-8'))
        csv_bytes.seek(0)
        
        # Hapus pesan waiting
        await waiting_msg.delete()
        
        # Kirim file
        waktu = format_waktu_wib()
        filename = f"produk_export_{waktu['tanggal'].replace('/', '')}_{waktu['jam'].replace(':', '')}.csv"
        
        await update.message.reply_document(
            document=csv_bytes,
            filename=filename,
            caption=(
                f"📊 *EXPORT DATA PRODUK (CSV)*\n\n"
                f"📅 Tanggal: {waktu['tanggal_lengkap']}\n"
                f"⏰ Jam: {waktu['jam']} WIB\n"
                f"📦 Total Produk: {len(produk_list)}\n\n"
                f"✅ Status:\n"
                f"• Aman: {len([p for p in produk_list if (datetime.strptime(p['tanggal'], '%Y-%m-%d').date() - today).days > 7])}\n"
                f"• Warning: {len([p for p in produk_list if 1 <= (datetime.strptime(p['tanggal'], '%Y-%m-%d').date() - today).days <= 7])}\n"
                f"• Expired: {len([p for p in produk_list if (datetime.strptime(p['tanggal'], '%Y-%m-%d').date() - today).days <= 0])}"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        print(f"Error export CSV: {e}")
        await waiting_msg.delete()
        await update.message.reply_text(
            f"❌ *Gagal membuat file CSV*\nError: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )

async def export_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export data produk ke file TXT"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await update.message.reply_text(
            "📭 *Tidak ada data untuk diexport*",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Kirim pesan proses
    waiting_msg = await update.message.reply_text(
        "⏳ *Sedang memproses export data...*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Buat file TXT
        today = datetime.now().date()
        waktu = format_waktu_wib()
        
        txt_content = f"""
========================================
      EXPORT DATA PRODUK EXPIRED
========================================
Tanggal Export : {waktu['tanggal_lengkap']}
Jam Export     : {waktu['jam']} WIB
Total Produk   : {len(produk_list)}
========================================

DAFTAR PRODUK:
"""
        
        for i, p in enumerate(produk_list, 1):
            expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
            selisih = (expired_date - today).days
            
            # Tentukan status
            if selisih < 0:
                status = f"EXPIRED ({abs(selisih)} hari)"
            elif selisih == 0:
                status = "EXPIRED HARI INI"
            elif selisih == 1:
                status = f"H-{selisih} (BESOK!)"
            elif selisih <= 3:
                status = f"H-{selisih}"
            elif selisih <= 7:
                status = f"H-{selisih}"
            else:
                status = f"AMAN ({selisih} hari)"
            
            txt_content += f"""
{i}. {p['nama']}
   Expired    : {expired_date.strftime('%d %B %Y')}
   Sisa Hari  : {selisih}
   Status     : {status}
   Kategori   : {p['kategori']}
   Lokasi     : {p['lokasi_detail']}
   Ditambahkan: {p.get('ditambahkan_jam', '-')} WIB - {p.get('ditambahkan_tanggal', '-')}
{'-'*40}
"""
        
        txt_content += f"""
========================================
STATISTIK:
- Aman (>7 hari)  : {len([p for p in produk_list if (datetime.strptime(p['tanggal'], '%Y-%m-%d').date() - today).days > 7])}
- Warning (H-7 s/d H-1) : {len([p for p in produk_list if 1 <= (datetime.strptime(p['tanggal'], '%Y-%m-%d').date() - today).days <= 7])}
- Expired         : {len([p for p in produk_list if (datetime.strptime(p['tanggal'], '%Y-%m-%d').date() - today).days <= 0])}
========================================
"""
        
        # Convert ke bytes
        txt_bytes = io.BytesIO()
        txt_bytes.write(txt_content.encode('utf-8'))
        txt_bytes.seek(0)
        
        # Hapus pesan waiting
        await waiting_msg.delete()
        
        # Kirim file
        filename = f"produk_export_{waktu['tanggal'].replace('/', '')}_{waktu['jam'].replace(':', '')}.txt"
        
        await update.message.reply_document(
            document=txt_bytes,
            filename=filename,
            caption=(
                f"📄 *EXPORT DATA PRODUK (TXT)*\n\n"
                f"📅 Tanggal: {waktu['tanggal_lengkap']}\n"
                f"⏰ Jam: {waktu['jam']} WIB\n"
                f"📦 Total Produk: {len(produk_list)}"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        print(f"Error export TXT: {e}")
        await waiting_msg.delete()
        await update.message.reply_text(
            f"❌ *Gagal membuat file TXT*\nError: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )

# ===================== NOTIFIKASI OTOMATIS =====================
async def cek_expired(context: ContextTypes.DEFAULT_TYPE):
    """Cek produk expired dan kirim notifikasi otomatis"""
    waktu_wib = get_waktu_wib()
    today = waktu_wib.date()
    print(f"🔔 Cek expired: {waktu_wib.strftime('%Y-%m-%d %H:%M:%S')} WIB")
    
    data = load_data()
    
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
                if selisih == 7 and notifikasi_terkirim.get(produk_id) != 7:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-7!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⏰ *Tersisa 7 hari lagi!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 7
                
                # NOTIFIKASI H-3
                elif selisih == 3 and notifikasi_terkirim.get(produk_id) != 3:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-3!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⏰ *Tersisa 3 hari lagi!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 3
                
                # NOTIFIKASI H-1
                elif selisih == 1 and notifikasi_terkirim.get(produk_id) != 1:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-1!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
                            f"🏷 *Kategori:* {produk.get('kategori', 'Umum')}\n\n"
                            f"⏰ *BESOK EXPIRED!*"
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
                            f"⚠️ *Sudah {abs(selisih)} hari expired!*"
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

# ===================== FUNGSI TAMBAHAN UNTUK MULAI TAMBAH =====================
async def tambah_mulai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses tambah produk via command"""
    await update.message.reply_text(
        "📦 *TAMBAH PRODUK BARU*\n\n"
        "Silakan masukkan *nama produk*:",
        parse_mode=ParseMode.MARKDOWN
    )
    return NAMA

async def tambah_mulai_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses tambah produk via callback"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📦 *TAMBAH PRODUK BARU*\n\n"
        "Silakan masukkan *nama produk*:",
        parse_mode=ParseMode.MARKDOWN
    )
    return NAMA

# ===================== MENU UTAMA =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu utama dengan tombol interaktif"""
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="tambah_produk")],
        [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="lihat_produk")],
        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="hapus_produk")],
        [InlineKeyboardButton("📊 STATISTIK", callback_data="statistik")],
        [InlineKeyboardButton("📍 CEK LOKASI", callback_data="cek_lokasi")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")],
        [InlineKeyboardButton("📝 EXPORT TXT", callback_data="export_txt")],
        [InlineKeyboardButton("❓ BANTUAN", callback_data="bantuan")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    waktu = format_waktu_wib()
    await update.message.reply_text(
        f"🏪 *MONITORING EXPIRED PRO* 🏪\n\n"
        f"🕒 *Waktu:* {waktu['jam']} WIB - {waktu['tanggal']}\n\n"
        f"Sistem manajemen expired dengan *lokasi bertingkat*:\n"
        f"• 📍 Plug-in 1-4 (Rak penyimpanan)\n"
        f"• 📍 Showcase 1-4 (Etalage display)\n\n"
        f"Pilih menu di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

# ===================== CALLBACK HANDLER UTAMA =====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua tombol callback"""
    query = update.callback_query
    await query.answer()
    
    # Menu utama
    if query.data == "tambah_produk":
        await query.edit_message_text(
            "📦 *TAMBAH PRODUK BARU*\n\n"
            "Silakan masukkan *nama produk*:",
            parse_mode=ParseMode.MARKDOWN
        )
        return NAMA
    
    elif query.data == "lihat_produk":
        await list_produk(update, context)
    
    elif query.data == "hapus_produk":
        await hapus_mulai(update, context)
    
    elif query.data == "statistik":
        await statistik(update, context)
    
    elif query.data == "cek_lokasi":
        await cek_lokasi(update, context)
    
    elif query.data == "export_csv":
        await export_csv_callback(update, context)
    
    elif query.data == "export_txt":
        await export_txt_callback(update, context)
    
    elif query.data == "bantuan":
        await bantuan(update, context)
    
    # Tombol kembali ke menu
    elif query.data == "kembali_ke_menu":
        keyboard = [
            [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="tambah_produk")],
            [InlineKeyboardButton("📋 LIHAT PRODUK", callback_data="lihat_produk")],
            [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="hapus_produk")],
            [InlineKeyboardButton("📊 STATISTIK", callback_data="statistik")],
            [InlineKeyboardButton("📍 CEK LOKASI", callback_data="cek_lokasi")],
            [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")],
            [InlineKeyboardButton("📝 EXPORT TXT", callback_data="export_txt")],
            [InlineKeyboardButton("❓ BANTUAN", callback_data="bantuan")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        waktu = format_waktu_wib()
        await query.edit_message_text(
            f"🏪 *MONITORING EXPIRED PRO* 🏪\n\n"
            f"🕒 *Waktu:* {waktu['jam']} WIB - {waktu['tanggal']}\n\n"
            f"Pilih menu di bawah:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    # Tombol untuk tambah produk (tipe lokasi)
    elif query.data == "tipe_plugin":
        # Pilih nomor plug-in
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
        return PLUGIN
    
    elif query.data == "tipe_showcase":
        # Pilih nomor showcase
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
        return SHOWCASE
    
    elif query.data == "kembali_tipe":
        # Kembali ke pilihan tipe lokasi
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
        return TIPE_LOKASI
    
    # Pilih nomor plug-in
    elif query.data.startswith("plugin_"):
        nomor = query.data.replace("plugin_", "")
        context.user_data['lokasi_tipe'] = "Plug-in"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Plug-in {nomor}"
        
        # Langsung ke pilih kategori
        keyboard = [
            [InlineKeyboardButton("🥛 Susu", callback_data="kategori_susu")],
            [InlineKeyboardButton("🥩 Daging", callback_data="kategori_daging")],
            [InlineKeyboardButton("🥦 Sayur", callback_data="kategori_sayur")],
            [InlineKeyboardButton("🍞 Roti", callback_data="kategori_roti")],
            [InlineKeyboardButton("🧃 Minuman", callback_data="kategori_minuman")],
            [InlineKeyboardButton("📦 Lainnya", callback_data="kategori_lain")],
            [InlineKeyboardButton("🔙 KEMBALI", callback_data="kembali_tipe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📍 *Lokasi:* {context.user_data['lokasi_detail']}\n\n"
            f"🏷 *PILIH KATEGORI PRODUK:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return KATEGORI
    
    # Pilih nomor showcase
    elif query.data.startswith("showcase_"):
        nomor = query.data.replace("showcase_", "")
        context.user_data['lokasi_tipe'] = "Showcase"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Showcase {nomor}"
        
        # Langsung ke pilih kategori
        keyboard = [
            [InlineKeyboardButton("🥛 Susu", callback_data="kategori_susu")],
            [InlineKeyboardButton("🥩 Daging", callback_data="kategori_daging")],
            [InlineKeyboardButton("🥦 Sayur", callback_data="kategori_sayur")],
            [InlineKeyboardButton("🍞 Roti", callback_data="kategori_roti")],
            [InlineKeyboardButton("🧃 Minuman", callback_data="kategori_minuman")],
            [InlineKeyboardButton("📦 Lainnya", callback_data="kategori_lain")],
            [InlineKeyboardButton("🔙 KEMBALI", callback_data="kembali_tipe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📍 *Lokasi:* {context.user_data['lokasi_detail']}\n\n"
            f"🏷 *PILIH KATEGORI PRODUK:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return KATEGORI
    
    # Pilih kategori
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
        await simpan_produk(update, context)
        return ConversationHandler.END
    
    # Hapus produk
    elif query.data.startswith("hapus_"):
        await hapus_produk(update, context)
    
    elif query.data == "batal_hapus":
        await query.edit_message_text("🚫 Penghapusan dibatalkan.")
        # Kembali ke menu
        keyboard = [
            [InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Kembali ke menu utama:",
            reply_markup=reply_markup
        )

# ===================== EXPORT VIA CALLBACK =====================
async def export_csv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export CSV via callback"""
    query = update.callback_query
    
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
    
    await query.edit_message_text(
        "⏳ *Sedang memproses export CSV...*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Buat file CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "No", "Nama Produk", "Tanggal Expired", "Sisa Hari", "Status",
            "Kategori", "Lokasi", "Tipe Lokasi", "Nomor",
            "Jam Ditambahkan", "Tanggal Ditambahkan"
        ])
        
        # Data
        today = datetime.now().date()
        for i, p in enumerate(produk_list, 1):
            expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
            selisih = (expired_date - today).days
            
            if selisih < 0:
                status = f"EXPIRED ({abs(selisih)} hari)"
            elif selisih == 0:
                status = "EXPIRED HARI INI"
            elif selisih == 1:
                status = f"H-{selisih} (BESOK!)"
            elif selisih <= 3:
                status = f"H-{selisih}"
            elif selisih <= 7:
                status = f"H-{selisih}"
            else:
                status = f"AMAN ({selisih} hari)"
            
            writer.writerow([
                i, p['nama'], expired_date.strftime('%d/%m/%Y'), selisih, status,
                p['kategori'], p['lokasi_detail'], p['lokasi_tipe'], p['lokasi_nomor'],
                p.get('ditambahkan_jam', '-'), p.get('ditambahkan_tanggal', '-')
            ])
        
        csv_data = output.getvalue()
        output.close()
        
        csv_bytes = io.BytesIO()
        csv_bytes.write(csv_data.encode('utf-8'))
        csv_bytes.seek(0)
        
        waktu = format_waktu_wib()
        filename = f"produk_export_{waktu['tanggal'].replace('/', '')}_{waktu['jam'].replace(':', '')}.csv"
        
        await query.message.reply_document(
            document=csv_bytes,
            filename=filename,
            caption=f"📊 *Export CSV*\nTotal: {len(produk_list)} produk",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await query.delete_message()
        
    except Exception as e:
        print(f"Error export CSV: {e}")
        await query.edit_message_text(
            f"❌ *Gagal export*\nError: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Tombol kembali
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

async def export_txt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export TXT via callback"""
    query = update.callback_query
    
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if not produk_list:
        await query.edit_message_text(
            "📭 *Tidak ada data untuk diexport*",
            parse_mode=ParseMode.MARKDOWN
        )
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
        return
    
    await query.edit_message_text(
        "⏳ *Sedang memproses export TXT...*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        today = datetime.now().date()
        waktu = format_waktu_wib()
        
        txt_content = f"""
========================================
      EXPORT DATA PRODUK EXPIRED
========================================
Tanggal Export : {waktu['tanggal_lengkap']}
Jam Export     : {waktu['jam']} WIB
Total Produk   : {len(produk_list)}
========================================

DAFTAR PRODUK:
"""
        
        for i, p in enumerate(produk_list, 1):
            expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
            selisih = (expired_date - today).days
            
            if selisih < 0:
                status = f"EXPIRED ({abs(selisih)} hari)"
            elif selisih == 0:
                status = "EXPIRED HARI INI"
            elif selisih == 1:
                status = f"H-{selisih} (BESOK!)"
            elif selisih <= 3:
                status = f"H-{selisih}"
            elif selisih <= 7:
                status = f"H-{selisih}"
            else:
                status = f"AMAN ({selisih} hari)"
            
            txt_content += f"""
{i}. {p['nama']}
   Expired    : {expired_date.strftime('%d %B %Y')}
   Sisa Hari  : {selisih}
   Status     : {status}
   Kategori   : {p['kategori']}
   Lokasi     : {p['lokasi_detail']}
   Ditambahkan: {p.get('ditambahkan_jam', '-')} WIB - {p.get('ditambahkan_tanggal', '-')}
{'-'*40}
"""
        
        txt_bytes = io.BytesIO()
        txt_bytes.write(txt_content.encode('utf-8'))
        txt_bytes.seek(0)
        
        filename = f"produk_export_{waktu['tanggal'].replace('/', '')}_{waktu['jam'].replace(':', '')}.txt"
        
        await query.message.reply_document(
            document=txt_bytes,
            filename=filename,
            caption=f"📄 *Export TXT*\nTotal: {len(produk_list)} produk",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await query.delete_message()
        
    except Exception as e:
        print(f"Error export TXT: {e}")
        await query.edit_message_text(
            f"❌ *Gagal export*\nError: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== TAMBAH PRODUK (MESSAGE HANDLER) =====================
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
            [InlineKeyboardButton("🪟 SHOWCASE (Etalase)", callback_data="tipe_showcase")],
            [InlineKeyboardButton("🔙 BATAL", callback_data="kembali_ke_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📍 *PILIH TIPE LOKASI:*",
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

async def simpan_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan produk ke database dengan waktu WIB"""
    if update.callback_query:
        query = update.callback_query
        user_id = update.effective_user.id
    else:
        user_id = update.effective_user.id
    
    # Ambil waktu WIB
    waktu = format_waktu_wib()
    
    produk = {
        "nama": context.user_data['nama'],
        "tanggal": context.user_data['tanggal'],
        "lokasi_tipe": context.user_data['lokasi_tipe'],
        "lokasi_nomor": context.user_data['lokasi_nomor'],
        "lokasi_detail": context.user_data['lokasi_detail'],
        "kategori": context.user_data['kategori'],
        "ditambahkan": waktu['full'],
        "ditambahkan_tanggal": waktu['tanggal'],
        "ditambahkan_jam": waktu['jam'],
        "ditambahkan_wib": True
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
    
    pesan = (
        f"✅ *PRODUK BERHASIL DITAMBAH!*\n\n"
        f"📦 *Nama:* {produk['nama']}\n"
        f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n"
        f"📊 *Status:* {status}\n"
        f"🏷 *Kategori:* {produk['kategori']}\n"
        f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
        f"⏰ *Ditambahkan:* {waktu['jam']} WIB - {waktu['tanggal']}\n\n"
        f"🔔 Notifikasi otomatis aktif: H-7, H-3, H-1"
    )
    
    if update.callback_query:
        await query.edit_message_text(pesan, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)
    
    # Tombol untuk aksi selanjutnya
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH LAGI", callback_data="tambah_produk")],
        [InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text(
            "Pilih aksi selanjutnya:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Pilih aksi selanjutnya:",
            reply_markup=reply_markup
        )
    
    context.user_data.clear()

# ===================== LIST PRODUK =====================
async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan semua produk"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
    else:
        reply_func = update.message.reply_text
    
    if not produk_list:
        await reply_func(
            "📭 *Belum ada produk*\n\n"
            "Gunakan menu TAMBAH PRODUK untuk menambahkan produk.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Urutkan berdasarkan tanggal (terdekat dulu)
        produk_list.sort(key=lambda x: x['tanggal'])
        
        today = datetime.now().date()
        pesan = "📋 *DAFTAR PRODUK*\n\n"
        
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
            
            pesan += f"{i}. {status} *{p['nama']}*\n"
            pesan += f"   📅 {expired_date.strftime('%d/%m/%Y')} ({selisih} hari)\n"
            pesan += f"   🏷 {p['kategori']}\n"
            pesan += f"   📍 {p['lokasi_detail']}\n"
            pesan += f"   ⏰ {p.get('ditambahkan_jam', '-')} WIB\n\n"
        
        pesan += f"📊 *Total: {len(produk_list)} produk*"
        await reply_func(pesan, parse_mode=ParseMode.MARKDOWN)
    
    # Tombol kembali
    keyboard = [
        [InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== STATISTIK =====================
async def statistik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan statistik lengkap"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
    else:
        reply_func = update.message.reply_text
    
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
    
    waktu = format_waktu_wib()
    pesan = f"📊 *STATISTIK PRODUK*\n"
    pesan += f"🕒 *{waktu['jam']} WIB - {waktu['tanggal']}*\n\n"
    pesan += "*STATUS EXPIRED:*\n"
    pesan += f"✅ Aman (>7 hari): {aman}\n"
    pesan += f"⚡ H-7 s/d H-4: {warning_h7}\n"
    pesan += f"⚠️ H-3 s/d H-2: {warning_h3}\n"
    pesan += f"🔥 H-1: {warning_h1}\n"
    pesan += f"⏰ Expired hari ini: {expired_hari_ini}\n"
    pesan += f"❌ Sudah expired: {expired}\n\n"
    
    if kategori:
        pesan += "*KATEGORI:*\n"
        for kat, jml in kategori.items():
            pesan += f"{kat}: {jml}\n"
        pesan += "\n"
    
    pesan += "*LOKASI:*\n"
    for lok, jml in {**lokasi_plugin, **lokasi_showcase}.items():
        if jml > 0:
            pesan += f"📍 {lok}: {jml} produk\n"
    
    pesan += f"\n📦 *TOTAL PRODUK: {len(produk_list)}*"
    
    await reply_func(pesan, parse_mode=ParseMode.MARKDOWN)
    
    # Tombol kembali
    keyboard = [
        [InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== CEK LOKASI =====================
async def cek_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek produk berdasarkan lokasi"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
    else:
        reply_func = update.message.reply_text
    
    if not produk_list:
        await reply_func(
            "📍 *CEK PRODUK PER LOKASI*\n\n"
            "Belum ada produk.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
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
        
        await reply_func(pesan, parse_mode=ParseMode.MARKDOWN)
    
    # Tombol kembali
    keyboard = [
        [InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== HAPUS PRODUK =====================
async def hapus_mulai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses hapus produk"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
    else:
        reply_func = update.message.reply_text
    
    if not produk_list:
        await reply_func(
            "📭 *Tidak ada produk untuk dihapus*",
            parse_mode=ParseMode.MARKDOWN
        )
        # Tombol kembali
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)
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
    
    await reply_func(
        "🗑 *HAPUS PRODUK*\n\nPilih produk yang akan dihapus:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def hapus_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hapus produk berdasarkan callback"""
    query = update.callback_query
    
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
    
    # Tombol kembali
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== BANTUAN =====================
async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan bantuan"""
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
    else:
        reply_func = update.message.reply_text
    
    await reply_func(
        "📚 *BANTUAN PENGGUNAAN*\n\n"
        "*PERINTAH:*\n"
        "/start - Menu utama\n"
        "/tambah - Tambah produk\n"
        "/list - Lihat semua produk\n"
        "/hapus - Hapus produk\n"
        "/stats - Statistik lengkap\n"
        "/lokasi - Cek per lokasi\n"
        "/export_csv - Export ke CSV\n"
        "/export_txt - Export ke TXT\n"
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
        "Contoh: 2026-12-31\n\n"
        
        "*EXPORT DATA:*\n"
        "📄 CSV : Bisa dibuka di Excel\n"
        "📝 TXT : Format teks biasa",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Tombol kembali
    keyboard = [
        [InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== MAIN =====================
def main():
    print("="*60)
    print("🏪 BOT EXPIRED PRO - EXPORT CSV/TXT")
    print("="*60)
    print(f"🤖 Token: {TOKEN[:15]}...")
    print("📊 Export CSV: AKTIF (tanpa openpyxl)")
    print("📝 Export TXT: AKTIF (tanpa openpyxl)")
    print("="*60)
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Job queue untuk notifikasi otomatis
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(cek_expired, interval=21600, first=10)
        print("⏰ Notifikasi otomatis: AKTIF (cek setiap 6 jam)")
    
    # Conversation handler untuk TAMBAH produk
    tambah_conv = ConversationHandler(
        entry_points=[
            CommandHandler('tambah', tambah_mulai),
            CallbackQueryHandler(tambah_mulai_callback, pattern="^tambah_produk$")
        ],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_produk)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_produk)],
            TIPE_LOKASI: [CallbackQueryHandler(button_callback)],
            PLUGIN: [CallbackQueryHandler(button_callback)],
            SHOWCASE: [CallbackQueryHandler(button_callback)],
            KATEGORI: [CallbackQueryHandler(button_callback)],
        },
        fallbacks=[
            CommandHandler('batal', lambda u,c: ConversationHandler.END),
            CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="^kembali_ke_menu$")
        ]
    )
    
    # Daftarkan semua handler
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('list', list_produk))
    app.add_handler(CommandHandler('stats', statistik))
    app.add_handler(CommandHandler('lokasi', cek_lokasi))
    app.add_handler(CommandHandler('export_csv', export_csv))
    app.add_handler(CommandHandler('export_txt', export_txt))
    app.add_handler(CommandHandler('bantuan', bantuan))
    app.add_handler(tambah_conv)
    
    # Callback query handler untuk yang bukan bagian dari conversation
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ BOT SIAP! Menjalankan polling...")
    print("📱 Cek Telegram Anda sekarang!")
    print("="*60)
    
    app.run_polling()

if __name__ == "__main__":
    main()
