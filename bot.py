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
import asyncio
from datetime import time
import pytz

# ===================== KONFIGURASI =====================
TOKEN = "8590161595:AAFQ2dSjsi_dKr61lvicnGkE2EAwMsusSCw"
DATA_FILE = "produk_database.json"
REMINDER_FILE = "reminder_status.json"

# ID Supervisor (GANTI DENGAN ID ANDA)
SUPERVISOR_IDS = [5285453784]  # ID Telegram Supri

# States untuk ConversationHandler
NAMA, TANGGAL, PIC, TIPE_LOKASI, PLUGIN, SHOWCASE = range(6)

# Status reminder global
PRODUCT_ACTION_STATUS = {}

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

# ===================== FUNGSI CEK SUPERVISOR =====================
async def cek_supervisor(user_id):
    """Cek apakah user adalah supervisor"""
    return user_id in SUPERVISOR_IDS

# ===================== FUNGSI EXPORT CSV =====================
async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export data produk ke file CSV"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    # Handle jika dipanggil dari callback
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
        message = query.message
    else:
        reply_func = update.message.reply_text
        message = update.message
    
    if not produk_list:
        await reply_func(
            "📭 *Tidak ada data untuk diexport*",
            parse_mode=ParseMode.MARKDOWN
        )
        # Tampilkan tombol kembali
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("Pilih menu:", reply_markup=reply_markup)
        return
    
    # Kirim pesan proses
    waiting_msg = await message.reply_text(
        "⏳ *Sedang memproses export data...*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "No", "Nama Produk", "Tanggal Expired", "Sisa Hari", "Status",
            "PIC", "Lokasi", "Tipe Lokasi", "Nomor",
            "Jam Ditambahkan", "Tanggal Ditambahkan"
        ])
        
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
                p.get('pic', '-'), p['lokasi_detail'], p['lokasi_tipe'], p['lokasi_nomor'],
                p.get('ditambahkan_jam', '-'), p.get('ditambahkan_tanggal', '-')
            ])
        
        csv_data = output.getvalue()
        output.close()
        
        csv_bytes = io.BytesIO()
        csv_bytes.write(csv_data.encode('utf-8'))
        csv_bytes.seek(0)
        
        await waiting_msg.delete()
        
        waktu = format_waktu_wib()
        filename = f"produk_export_{waktu['tanggal'].replace('/', '')}_{waktu['jam'].replace(':', '')}.csv"
        
        await message.reply_document(
            document=csv_bytes,
            filename=filename,
            caption=(
                f"📊 *EXPORT DATA PRODUK (CSV)*\n\n"
                f"📅 Tanggal: {waktu['tanggal_lengkap']}\n"
                f"⏰ Jam: {waktu['jam']} WIB\n"
                f"📦 Total Produk: {len(produk_list)}"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        print(f"Error export CSV: {e}")
        await waiting_msg.delete()
        await message.reply_text(
            f"❌ *Gagal membuat file CSV*\nError: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Tombol kembali setelah export
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("Pilih menu:", reply_markup=reply_markup)

async def export_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export data produk ke file TXT"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    # Handle jika dipanggil dari callback
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
        message = query.message
    else:
        reply_func = update.message.reply_text
        message = update.message
    
    if not produk_list:
        await reply_func(
            "📭 *Tidak ada data untuk diexport*",
            parse_mode=ParseMode.MARKDOWN
        )
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("Pilih menu:", reply_markup=reply_markup)
        return
    
    waiting_msg = await message.reply_text(
        "⏳ *Sedang memproses export data...*",
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
   PIC        : {p.get('pic', '-')}
   Lokasi     : {p['lokasi_detail']}
   Ditambahkan: {p.get('ditambahkan_jam', '-')} WIB - {p.get('ditambahkan_tanggal', '-')}
{'-'*40}
"""
        
        txt_bytes = io.BytesIO()
        txt_bytes.write(txt_content.encode('utf-8'))
        txt_bytes.seek(0)
        
        await waiting_msg.delete()
        
        filename = f"produk_export_{waktu['tanggal'].replace('/', '')}_{waktu['jam'].replace(':', '')}.txt"
        
        await message.reply_document(
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
        await message.reply_text(
            f"❌ *Gagal membuat file TXT*\nError: {str(e)[:100]}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Tombol kembali setelah export
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== FUNGSI NOTIFIKASI DENGAN REMINDER =====================
async def cek_expired_dengan_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Cek expired dengan sistem reminder 3 jam jika belum ditindaklanjuti"""
    global PRODUCT_ACTION_STATUS
    
    waktu_wib = get_waktu_wib()
    today = waktu_wib.date()
    jam_sekarang = waktu_wib.hour
    menit_sekarang = waktu_wib.minute
    
    print(f"🔔 Cek expired: {waktu_wib.strftime('%Y-%m-%d %H:%M:%S')} WIB")
    
    data = load_data()
    
    # RESET HARIAN: jam 06:00 pagi
    if jam_sekarang == 6 and menit_sekarang < 5:
        print("🔄 RESET HARIAN: Membersihkan status tindak lanjut")
        PRODUCT_ACTION_STATUS.clear()
        try:
            with open(REMINDER_FILE, 'w') as f:
                json.dump({}, f)
        except:
            pass
    
    for user_id_str, user_data in data.items():
        produk_list = user_data.get("produk", [])
        notifikasi_terkirim = user_data.get("notifikasi", {})
        notifikasi_baru = {}
        
        for produk in produk_list:
            try:
                expired_date = datetime.strptime(produk['tanggal'], '%Y-%m-%d').date()
                selisih = (expired_date - today).days
                produk_id = f"{produk['nama']}_{produk['tanggal']}"
                status_key = f"{user_id_str}_{produk_id}"
                
                # ===== PRODUK SUDAH EXPIRED =====
                if selisih < 0:
                    sudah_ditindak = PRODUCT_ACTION_STATUS.get(status_key, {}).get("action_taken", False)
                    
                    if not sudah_ditindak:
                        last_reminder = PRODUCT_ACTION_STATUS.get(status_key, {}).get("last_reminder", None)
                        reminder_count = PRODUCT_ACTION_STATUS.get(status_key, {}).get("reminder_count", 0)
                        
                        kirim_reminder = False
                        
                        if last_reminder is None:
                            kirim_reminder = True
                        else:
                            selisih_jam = (waktu_wib - last_reminder).total_seconds() / 3600
                            if selisih_jam >= 3:
                                kirim_reminder = True
                        
                        if kirim_reminder:
                            keyboard = [
                                [InlineKeyboardButton("✅ SUDAH DITINDAKLANJUTI", callback_data=f"tindak_{user_id_str}_{produk_id}")],
                                [InlineKeyboardButton("📸 FOTO DOKUMENTASI", callback_data=f"foto_{user_id_str}_{produk_id}")],
                                [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data=f"hapus_{produk_id}")]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            hari_expired = abs(selisih)
                            if hari_expired == 0:
                                status_text = "EXPIRED HARI INI"
                            else:
                                status_text = f"SUDAH {hari_expired} HARI EXPIRED"
                            
                            await context.bot.send_message(
                                chat_id=int(user_id_str),
                                text=(
                                    f"❌ *PRODUK SUDAH EXPIRED!*\n\n"
                                    f"📦 *Produk:* {produk['nama']}\n"
                                    f"👤 *PIC:* {produk.get('pic', '-')}\n"
                                    f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                                    f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n\n"
                                    f"⚠️ *{status_text}*\n"
                                    f"⏰ *Notifikasi ke-{reminder_count + 1}*\n\n"
                                    f"🔔 *Jika belum ditindaklanjuti, notifikasi akan muncul lagi 3 jam kemudian.*"
                                ),
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=reply_markup
                            )
                            
                            PRODUCT_ACTION_STATUS[status_key] = {
                                "last_reminder": waktu_wib,
                                "action_taken": False,
                                "reminder_count": reminder_count + 1
                            }
                    
                    if notifikasi_terkirim.get(produk_id) != "expired":
                        notifikasi_baru[produk_id] = "expired"
                
                # ===== H-7 =====
                elif selisih == 7 and notifikasi_terkirim.get(produk_id) != 7:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-7!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"👤 *PIC:* {produk.get('pic', '-')}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n\n"
                            f"⏰ *Tersisa 7 hari lagi!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 7
                
                # ===== H-3 =====
                elif selisih == 3 and notifikasi_terkirim.get(produk_id) != 3:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-3!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"👤 *PIC:* {produk.get('pic', '-')}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n\n"
                            f"⏰ *Tersisa 3 hari lagi!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 3
                
                # ===== H-1 =====
                elif selisih == 1 and notifikasi_terkirim.get(produk_id) != 1:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"⚠️ *PERINGATAN H-1!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"👤 *PIC:* {produk.get('pic', '-')}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n\n"
                            f"⏰ *BESOK EXPIRED!*"
                        ),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    notifikasi_baru[produk_id] = 1
                
                # ===== EXPIRED HARI INI =====
                elif selisih == 0 and notifikasi_terkirim.get(produk_id) != "expired_hari_ini":
                    keyboard = [
                        [InlineKeyboardButton("✅ SUDAH DITINDAKLANJUTI", callback_data=f"tindak_{user_id_str}_{produk_id}")],
                        [InlineKeyboardButton("📸 FOTO DOKUMENTASI", callback_data=f"foto_{user_id_str}_{produk_id}")],
                        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data=f"hapus_{produk_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=(
                            f"❌ *EXPIRED HARI INI!*\n\n"
                            f"📦 *Produk:* {produk['nama']}\n"
                            f"👤 *PIC:* {produk.get('pic', '-')}\n"
                            f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
                            f"📅 *Expired:* {expired_date.strftime('%d %B %Y')}\n\n"
                            f"⚠️ *Produk sudah expired hari ini!*\n\n"
                            f"🔔 *Jika belum ditindaklanjuti, notifikasi akan muncul lagi 3 jam kemudian.*"
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=reply_markup
                    )
                    notifikasi_baru[produk_id] = "expired_hari_ini"
                
                else:
                    if produk_id in notifikasi_terkirim:
                        notifikasi_baru[produk_id] = notifikasi_terkirim[produk_id]
                        
            except Exception as e:
                print(f"Error notifikasi: {e}")
        
        user_data["notifikasi"] = notifikasi_baru
        save_user_data(user_id_str, user_data)
    
    # Simpan status reminder
    try:
        status_serializable = {}
        for key, value in PRODUCT_ACTION_STATUS.items():
            status_serializable[key] = {
                "last_reminder": value["last_reminder"].isoformat() if value["last_reminder"] else None,
                "action_taken": value["action_taken"],
                "reminder_count": value["reminder_count"]
            }
        with open(REMINDER_FILE, 'w') as f:
            json.dump(status_serializable, f)
    except Exception as e:
        print(f"Error saving reminder status: {e}")

# ===================== HANDLER TINDAK LANJUT =====================
async def tindak_lanjut_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle tombol 'SUDAH DITINDAKLANJUTI'"""
    global PRODUCT_ACTION_STATUS
    
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("_")
    user_id = data[1]
    produk_id = "_".join(data[2:])
    status_key = f"{user_id}_{produk_id}"
    
    if status_key in PRODUCT_ACTION_STATUS:
        PRODUCT_ACTION_STATUS[status_key]["action_taken"] = True
    
    await query.edit_message_text(
        f"✅ *Tindak lanjut tercatat!*\n\n"
        f"Produk telah ditandai sebagai 'SUDAH DITINDAKLANJUTI'.\n"
        f"Notifikasi untuk produk ini akan berhenti.\n\n"
        f"Terima kasih telah memproses produk expired.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    keyboard = [
        [InlineKeyboardButton("🗑 HAPUS PRODUK DARI DATABASE", callback_data=f"hapus_{produk_id}")],
        [InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "Langkah selanjutnya:",
        reply_markup=reply_markup
    )

# ===================== FUNGSI TAMBAHAN PRODUK =====================
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
        
        await update.message.reply_text(
            "👤 *Masukkan nama PIC (Penanggung Jawab):*\n\n"
            "Contoh: Supri, Angga, Andre, Budi, dll\n\n"
            "Silakan ketik nama PIC:",
            parse_mode=ParseMode.MARKDOWN
        )
        return PIC
    except:
        await update.message.reply_text(
            "❌ Format salah! Gunakan YYYY-MM-DD\n"
            "Contoh: 2026-12-31"
        )
        return TANGGAL

async def pic_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima input nama PIC"""
    context.user_data['pic'] = update.message.text
    
    keyboard = [
        [InlineKeyboardButton("📦 PLUG-IN (Rak 1-35)", callback_data="tipe_plugin")],
        [InlineKeyboardButton("🪟 SHOWCASE (Etalase 1-10)", callback_data="tipe_showcase")],
        [InlineKeyboardButton("🔙 BATAL", callback_data="kembali_ke_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👤 *PIC:* {context.user_data['pic']}\n\n"
        f"📍 *PILIH TIPE LOKASI:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return TIPE_LOKASI

async def simpan_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simpan produk ke database"""
    if update.callback_query:
        query = update.callback_query
        user_id = update.effective_user.id
    else:
        user_id = update.effective_user.id
    
    waktu = format_waktu_wib()
    
    produk = {
        "nama": context.user_data['nama'],
        "tanggal": context.user_data['tanggal'],
        "pic": context.user_data['pic'],
        "lokasi_tipe": context.user_data['lokasi_tipe'],
        "lokasi_nomor": context.user_data['lokasi_nomor'],
        "lokasi_detail": context.user_data['lokasi_detail'],
        "ditambahkan": waktu['full'],
        "ditambahkan_tanggal": waktu['tanggal'],
        "ditambahkan_jam": waktu['jam'],
        "ditambahkan_wib": True
    }
    
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
        f"👤 *PIC:* {produk['pic']}\n"
        f"📍 *Lokasi:* {produk['lokasi_detail']}\n"
        f"⏰ *Ditambahkan:* {waktu['jam']} WIB - {waktu['tanggal']}"
    )
    
    if update.callback_query:
        await query.edit_message_text(pesan, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(pesan, parse_mode=ParseMode.MARKDOWN)
    
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH LAGI", callback_data="tambah_produk")],
        [InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text("Pilih aksi selanjutnya:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pilih aksi selanjutnya:", reply_markup=reply_markup)
    
    context.user_data.clear()

# ===================== LIST PRODUK =====================
async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan semua produk user"""
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
            "📭 *Belum ada produk*",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
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
            pesan += f"   👤 PIC: {p.get('pic', '-')}\n"
            pesan += f"   📍 {p['lokasi_detail']}\n\n"
        
        pesan += f"📊 *Total: {len(produk_list)} produk*"
        await reply_func(pesan, parse_mode=ParseMode.MARKDOWN)
    
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== STATISTIK =====================
async def statistik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistik produk user"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    produk_list = user_data.get("produk", [])
    
    if update.callback_query:
        query = update.callback_query
        reply_func = query.edit_message_text
    else:
        reply_func = update.message.reply_text
    
    today = datetime.now().date()
    
    aman = warning_h7 = warning_h3 = warning_h1 = expired_hari_ini = expired = 0
    
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
    
    waktu = format_waktu_wib()
    pesan = f"📊 *STATISTIK PRODUK ANDA*\n"
    pesan += f"🕒 *{waktu['jam']} WIB - {waktu['tanggal']}*\n\n"
    pesan += f"✅ Aman (>7 hari): {aman}\n"
    pesan += f"⚡ H-7 s/d H-4: {warning_h7}\n"
    pesan += f"⚠️ H-3 s/d H-2: {warning_h3}\n"
    pesan += f"🔥 H-1: {warning_h1}\n"
    pesan += f"⏰ Expired hari ini: {expired_hari_ini}\n"
    pesan += f"❌ Sudah expired: {expired}\n"
    pesan += f"\n📦 *TOTAL: {len(produk_list)} produk*"
    
    await reply_func(pesan, parse_mode=ParseMode.MARKDOWN)
    
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
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
        await reply_func("📍 *Belum ada produk*", parse_mode=ParseMode.MARKDOWN)
    else:
        lokasi_dict = {}
        for p in produk_list:
            lokasi = p['lokasi_detail']
            if lokasi not in lokasi_dict:
                lokasi_dict[lokasi] = []
            lokasi_dict[lokasi].append(p)
        
        pesan = "📍 *PRODUK PER LOKASI*\n\n"
        for lokasi in sorted(lokasi_dict.keys()):
            pesan += f"*{lokasi}:* {len(lokasi_dict[lokasi])} produk\n"
            for p in lokasi_dict[lokasi]:
                expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
                pesan += f"  • {p['nama']} ({expired_date.strftime('%d/%m')})\n"
            pesan += "\n"
        
        await reply_func(pesan, parse_mode=ParseMode.MARKDOWN)
    
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
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
        await reply_func("📭 *Tidak ada produk*", parse_mode=ParseMode.MARKDOWN)
        keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)
        return
    
    keyboard = []
    for i, p in enumerate(produk_list, 1):
        expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
        keyboard.append([InlineKeyboardButton(
            f"{i}. {p['nama']} ({expired_date.strftime('%d/%m')})",
            callback_data=f"hapus_{i-1}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ BATAL", callback_data="batal_hapus")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await reply_func(
        "🗑 *HAPUS PRODUK*\n\nPilih produk:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def hapus_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hapus produk dari database"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Handle hapus dari notifikasi (format: hapus_produk_id)
    if query.data.startswith("hapus_") and len(query.data.split("_")) > 2:
        produk_id = "_".join(query.data.split("_")[1:])
        
        semua_data = load_data()
        ditemukan = False
        
        for uid, user_data in semua_data.items():
            for i, p in enumerate(user_data.get("produk", [])):
                pid = f"{p['nama']}_{p['tanggal']}"
                if pid == produk_id:
                    produk_hapus = user_data["produk"].pop(i)
                    save_user_data(uid, user_data)
                    ditemukan = True
                    break
            if ditemukan:
                break
        
        if ditemukan:
            await query.edit_message_text(
                f"✅ *Produk berhasil dihapus!*\n\n"
                f"Nama: {produk_hapus['nama']}\n"
                f"PIC: {produk_hapus.get('pic', '-')}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text("❌ Produk tidak ditemukan")
    
    # Handle hapus dari menu (format: hapus_index)
    else:
        index = int(query.data.replace("hapus_", ""))
        user_data = get_user_data(user_id)
        produk_hapus = user_data["produk"].pop(index)
        save_user_data(user_id, user_data)
        
        await query.edit_message_text(
            f"✅ *Produk berhasil dihapus!*\n\n"
            f"Nama: {produk_hapus['nama']}\n"
            f"PIC: {produk_hapus.get('pic', '-')}",
            parse_mode=ParseMode.MARKDOWN
        )
    
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
        "📚 *BANTUAN*\n\n"
        "*/start* - Menu utama\n"
        "*/tambah* - Tambah produk\n"
        "*/list* - Lihat produk saya\n"
        "*/stats* - Statistik saya\n"
        "*/hapus* - Hapus produk\n"
        "*/lokasi* - Cek per lokasi\n"
        "*/export_csv* - Export CSV\n"
        "*/export_txt* - Export TXT\n\n"
        "⏰ *Notifikasi:*\n"
        "• H-7, H-3, H-1, expired\n"
        "• Mulai jam 06:00 pagi\n"
        "• Reminder 3 jam jika belum ditindak",
        parse_mode=ParseMode.MARKDOWN
    )
    
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== FITUR SUPERVISOR =====================
async def menu_pintar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu yang menyesuaikan role user (dari command)"""
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="tambah_produk")],
        [InlineKeyboardButton("📋 PRODUK SAYA", callback_data="lihat_produk")],
        [InlineKeyboardButton("📊 STATISTIK SAYA", callback_data="statistik")],
    ]
    
    if await cek_supervisor(user_id):
        keyboard.extend([
            [InlineKeyboardButton("👑 SEMUA PRODUK", callback_data="lihat_semua_produk")],
            [InlineKeyboardButton("📊 STATISTIK SEMUA", callback_data="statistik_semua")],
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("📍 CEK LOKASI", callback_data="cek_lokasi")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")],
        [InlineKeyboardButton("📝 EXPORT TXT", callback_data="export_txt")],
        [InlineKeyboardButton("❓ BANTUAN", callback_data="bantuan")],
        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="hapus_produk")],
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    waktu = format_waktu_wib()
    role = "👑 SUPERVISOR + PIC" if await cek_supervisor(user_id) else "👤 PIC"
    
    await update.message.reply_text(
        f"🏪 *MONITORING EXPIRED PRO* 🏪\n\n"
        f"🕒 *Waktu:* {waktu['jam']} WIB - {waktu['tanggal']}\n"
        f"{role}\n\n"
        f"Pilih menu di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def menu_pintar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu yang menyesuaikan role user (dipanggil dari callback)"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("📦 TAMBAH PRODUK", callback_data="tambah_produk")],
        [InlineKeyboardButton("📋 PRODUK SAYA", callback_data="lihat_produk")],
        [InlineKeyboardButton("📊 STATISTIK SAYA", callback_data="statistik")],
    ]
    
    if await cek_supervisor(user_id):
        keyboard.extend([
            [InlineKeyboardButton("👑 SEMUA PRODUK", callback_data="lihat_semua_produk")],
            [InlineKeyboardButton("📊 STATISTIK SEMUA", callback_data="statistik_semua")],
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("📍 CEK LOKASI", callback_data="cek_lokasi")],
        [InlineKeyboardButton("📄 EXPORT CSV", callback_data="export_csv")],
        [InlineKeyboardButton("📝 EXPORT TXT", callback_data="export_txt")],
        [InlineKeyboardButton("❓ BANTUAN", callback_data="bantuan")],
        [InlineKeyboardButton("🗑 HAPUS PRODUK", callback_data="hapus_produk")],
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    waktu = format_waktu_wib()
    role = "👑 SUPERVISOR + PIC" if await cek_supervisor(user_id) else "👤 PIC"
    
    await query.edit_message_text(
        f"🏪 *MONITORING EXPIRED PRO* 🏪\n\n"
        f"🕒 *Waktu:* {waktu['jam']} WIB - {waktu['tanggal']}\n"
        f"{role}\n\n"
        f"Pilih menu di bawah:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def lihat_semua_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lihat semua produk semua PIC (khusus supervisor)"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not await cek_supervisor(user_id):
        await query.answer("❌ Anda tidak punya akses!", show_alert=True)
        return
    
    semua_data = load_data()
    pesan = "👑 *SEMUA PRODUK (SEMUA PIC)*\n\n"
    total = 0
    today = datetime.now().date()
    
    for uid, data in semua_data.items():
        produk = data.get("produk", [])
        if produk:
            pic_name = produk[0].get('pic', 'Unknown')
            pesan += f"*👤 {pic_name}* ({len(produk)} produk):\n"
            produk.sort(key=lambda x: x['tanggal'])
            
            for p in produk[:5]:
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
                
                pesan += f"  {status} {p['nama']} - {p['lokasi_detail']} ({expired_date.strftime('%d/%m')})\n"
            
            if len(produk) > 5:
                pesan += f"  ... dan {len(produk)-5} lainnya\n"
            pesan += "\n"
            total += len(produk)
    
    pesan += f"📦 *TOTAL: {total} produk*"
    
    if len(pesan) > 4000:
        parts = [pesan[i:i+4000] for i in range(0, len(pesan), 4000)]
        for part in parts:
            await query.edit_message_text(part, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(pesan, parse_mode=ParseMode.MARKDOWN)
    
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

async def statistik_semua(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistik semua PIC (khusus supervisor)"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not await cek_supervisor(user_id):
        await query.answer("❌ Anda tidak punya akses!", show_alert=True)
        return
    
    semua_data = load_data()
    today = datetime.now().date()
    
    pic_stats = {}
    total_produk = 0
    
    for uid, data in semua_data.items():
        produk = data.get("produk", [])
        if produk:
            pic_name = produk[0].get('pic', 'Unknown')
            pic_stats[pic_name] = {
                'total': len(produk),
                'expired': 0
            }
            
            for p in produk:
                expired_date = datetime.strptime(p['tanggal'], '%Y-%m-%d').date()
                if (expired_date - today).days < 0:
                    pic_stats[pic_name]['expired'] += 1
            
            total_produk += len(produk)
    
    waktu = format_waktu_wib()
    pesan = f"👑 *STATISTIK SEMUA PIC*\n"
    pesan += f"🕒 *{waktu['jam']} WIB - {waktu['tanggal']}*\n\n"
    
    for pic, stats in sorted(pic_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        pesan += f"*👤 {pic}*\n"
        pesan += f"  📦 Total: {stats['total']} produk\n"
        pesan += f"  ❌ Expired: {stats['expired']} produk\n"
        
        if stats['total'] > 0:
            persen = (stats['expired'] / stats['total']) * 100
            if persen < 5:
                star = "⭐ BAGUS"
            elif persen < 10:
                star = "⚠️ CUKUP"
            else:
                star = "❌ PERLU EVALUASI"
            pesan += f"  {star} ({persen:.1f}%)\n\n"
    
    pesan += f"\n📦 *TOTAL KESELURUHAN: {total_produk} produk*"
    
    await query.edit_message_text(pesan, parse_mode=ParseMode.MARKDOWN)
    
    keyboard = [[InlineKeyboardButton("🏠 KEMBALI KE MENU", callback_data="kembali_ke_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Pilih menu:", reply_markup=reply_markup)

# ===================== MAIN =====================
def main():
    print("="*60)
    print("🏪 BOT EXPIRED PRO - DENGAN SUPERVISOR + REMINDER")
    print("="*60)
    print(f"🤖 Token: {TOKEN[:15]}...")
    print(f"👑 Supervisor ID: {SUPERVISOR_IDS}")
    print("👤 Fitur PIC: AKTIF")
    print("📍 Plug-in: 1-35, Showcase: 1-10")
    print("⏰ Notifikasi: Mulai 06:00 WIB, Reminder 3 jam")
    print("📊 Export CSV: AKTIF (dengan kolom PIC)")
    print("="*60)
    
    # Load status reminder
    global PRODUCT_ACTION_STATUS
    try:
        if os.path.exists(REMINDER_FILE):
            with open(REMINDER_FILE, 'r') as f:
                status_loaded = json.load(f)
                for key, value in status_loaded.items():
                    PRODUCT_ACTION_STATUS[key] = {
                        "last_reminder": datetime.fromisoformat(value["last_reminder"]) if value["last_reminder"] else None,
                        "action_taken": value["action_taken"],
                        "reminder_count": value["reminder_count"]
                    }
            print("✅ Status reminder berhasil diload")
    except Exception as e:
        print(f"⚠️ Gagal load reminder status: {e}")
        PRODUCT_ACTION_STATUS = {}
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Job queue untuk notifikasi
    job_queue = app.job_queue
    if job_queue:
        # Notifikasi utama jam 06:00 pagi
        job_queue.run_daily(
            cek_expired_dengan_reminder,
            time(hour=6, minute=0, tzinfo=pytz.timezone('Asia/Jakarta'))
        )
        # Backup setiap 3 jam untuk reminder
        job_queue.run_repeating(cek_expired_dengan_reminder, interval=10800, first=3600)
        print("⏰ Notifikasi: 06:00 WIB + reminder 3 jam")
    
    # Conversation handler
    tambah_conv = ConversationHandler(
        entry_points=[
            CommandHandler('tambah', tambah_mulai),
            CallbackQueryHandler(tambah_mulai_callback, pattern="^tambah_produk$")
        ],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_produk)],
            TANGGAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanggal_produk)],
            PIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, pic_produk)],
            TIPE_LOKASI: [CallbackQueryHandler(button_callback)],
            PLUGIN: [CallbackQueryHandler(button_callback)],
            SHOWCASE: [CallbackQueryHandler(button_callback)],
        },
        fallbacks=[
            CommandHandler('batal', lambda u,c: ConversationHandler.END),
            CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="^kembali_ke_menu$")
        ]
    )
    
    # Register handlers
    app.add_handler(CommandHandler('start', menu_pintar))
    app.add_handler(CommandHandler('list', list_produk))
    app.add_handler(CommandHandler('stats', statistik))
    app.add_handler(CommandHandler('lokasi', cek_lokasi))
    app.add_handler(CommandHandler('export_csv', export_csv))
    app.add_handler(CommandHandler('export_txt', export_txt))
    app.add_handler(CommandHandler('bantuan', bantuan))
    app.add_handler(CommandHandler('semua', lihat_semua_produk))
    app.add_handler(CommandHandler('stat_all', statistik_semua))
    app.add_handler(tambah_conv)
    
    # Callback query handler harus di paling akhir
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Handler foto
    async def foto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.photo and 'foto_produk_id' in context.user_data:
            photo_file = await update.message.photo[-1].get_file()
            produk_id = context.user_data['foto_produk_id']
            user_id = context.user_data['foto_user_id']
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"foto_expired_{produk_id}_{timestamp}.jpg"
            await photo_file.download_to_drive(filename)
            
            await update.message.reply_text(
                f"✅ *Foto tersimpan!*\n\nFile: {filename}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("✅ SUDAH DITINDAKLANJUTI", callback_data=f"tindak_{user_id}_{produk_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Konfirmasi tindak lanjut:", reply_markup=reply_markup)
            
            del context.user_data['foto_produk_id']
            del context.user_data['foto_user_id']
    
    app.add_handler(MessageHandler(filters.PHOTO, foto_handler))
    
    print("✅ BOT SIAP! Menjalankan polling...")
    print("="*60)
    
    app.run_polling()

# ===================== CALLBACK HANDLER =====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua tombol callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "tambah_produk":
        await query.edit_message_text(
            "📦 *TAMBAH PRODUK BARU*\n\nSilakan masukkan *nama produk*:",
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
        await export_csv(update, context)
    
    elif query.data == "export_txt":
        await export_txt(update, context)
    
    elif query.data == "bantuan":
        await bantuan(update, context)
    
    elif query.data == "kembali_ke_menu":
        await menu_pintar_callback(update, context)
        return ConversationHandler.END
    
    elif query.data == "lihat_semua_produk":
        await lihat_semua_produk(update, context)
    
    elif query.data == "statistik_semua":
        await statistik_semua(update, context)
    
    elif query.data.startswith("tindak_"):
        await tindak_lanjut_callback(update, context)
    
    elif query.data.startswith("foto_"):
        data = query.data.split("_")
        context.user_data['foto_produk_id'] = "_".join(data[2:])
        context.user_data['foto_user_id'] = data[1]
        await query.edit_message_text(
            "📸 *FOTO DOKUMENTASI*\n\nSilakan kirim foto produk expired.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data.startswith("hapus_"):
        await hapus_produk(update, context)
    
    elif query.data == "batal_hapus":
        await query.edit_message_text("🚫 Dibatalkan.")
        keyboard = [[InlineKeyboardButton("🏠 MENU UTAMA", callback_data="kembali_ke_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Kembali ke menu:", reply_markup=reply_markup)
    
    elif query.data == "tipe_plugin":
        keyboard = []
        for i in range(1, 36, 5):
            row = []
            for j in range(i, min(i+5, 36)):
                row.append(InlineKeyboardButton(f"📦 {j}", callback_data=f"plugin_{j}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 KEMBALI", callback_data="kembali_tipe")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH NOMOR PLUG-IN (1-35):*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return PLUGIN
    
    elif query.data == "tipe_showcase":
        keyboard = []
        for i in range(1, 11, 5):
            row = []
            for j in range(i, min(i+5, 11)):
                row.append(InlineKeyboardButton(f"🪟 {j}", callback_data=f"showcase_{j}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 KEMBALI", callback_data="kembali_tipe")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH NOMOR SHOWCASE (1-10):*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return SHOWCASE
    
    elif query.data == "kembali_tipe":
        keyboard = [
            [InlineKeyboardButton("📦 PLUG-IN (1-35)", callback_data="tipe_plugin")],
            [InlineKeyboardButton("🪟 SHOWCASE (1-10)", callback_data="tipe_showcase")],
            [InlineKeyboardButton("🔙 BATAL", callback_data="kembali_ke_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📍 *PILIH TIPE LOKASI:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return TIPE_LOKASI
    
    elif query.data.startswith("plugin_"):
        nomor = query.data.replace("plugin_", "")
        context.user_data['lokasi_tipe'] = "Plug-in"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Plug-in {nomor}"
        await simpan_produk(update, context)
        return ConversationHandler.END
    
    elif query.data.startswith("showcase_"):
        nomor = query.data.replace("showcase_", "")
        context.user_data['lokasi_tipe'] = "Showcase"
        context.user_data['lokasi_nomor'] = nomor
        context.user_data['lokasi_detail'] = f"Showcase {nomor}"
        await simpan_produk(update, context)
        return ConversationHandler.END

if __name__ == "__main__":
    main()
