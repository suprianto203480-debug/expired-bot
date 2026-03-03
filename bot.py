import os
import logging
import psycopg2
import csv
import pytz
from datetime import datetime, date
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ===== ADMIN LIST =====
ADMIN_IDS = [5285453784]

PILIH_LOKASI, CARI_PRODUK, PILIH_PRODUK, INPUT_EXPIRED, TAMBAH_LAGI = range(5)

# ================= DATABASE =================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def get_user_by_telegram_id(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT username, nama, role, is_active
            FROM users
            WHERE telegram_id = %s
        """, (telegram_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def user_exists(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT nama FROM users WHERE telegram_id=%s AND is_active=true", (telegram_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def get_locations():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id,nama_lokasi FROM locations WHERE is_active=true ORDER BY id")
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def search_product(keyword):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT upc, sku, deskripsi
            FROM products
            WHERE upc ILIKE %s OR sku::text ILIKE %s OR deskripsi ILIKE %s
            LIMIT 10
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
        rows = cur.fetchall()
        return [{"upc": r[0], "sku": r[1], "nama_produk": r[2]} for r in rows]
    finally:
        cur.close()
        conn.close()

def save_expired(lokasi_id, upc, nama_produk, expired_date, pic):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO expired_logs
            (tanggal_input,lokasi,upc,nama_produk,expired_date,pic)
            VALUES ((NOW() AT TIME ZONE 'Asia/Jakarta'),%s,%s,%s,%s,%s)
        """, (lokasi_id, upc, nama_produk, expired_date, pic))
        conn.commit()
    finally:
        cur.close()
        conn.close()

def get_today_expired():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT l.nama_lokasi,
                   p.sku,
                   e.nama_produk,
                   e.upc,
                   e.expired_date,
                   e.pic,
                   e.tanggal_input
            FROM expired_logs e
            LEFT JOIN locations l ON l.id::text = e.lokasi::text
            LEFT JOIN products p ON p.upc::text = e.upc::text
            WHERE (e.tanggal_input AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Jakarta')::date
                  = (NOW() AT TIME ZONE 'Asia/Jakarta')::date
            ORDER BY l.nama_lokasi, p.sku
        """)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def get_monthly_report(year, month):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                l.nama_lokasi,
                p.sku,
                e.nama_produk,
                e.upc,
                e.expired_date,
                e.pic,
                e.tanggal_input
            FROM expired_logs e
            LEFT JOIN locations l ON l.id::text = e.lokasi::text
            LEFT JOIN products p ON p.upc::text = e.upc::text
            WHERE EXTRACT(YEAR FROM e.tanggal_input AT TIME ZONE 'Asia/Jakarta') = %s
              AND EXTRACT(MONTH FROM e.tanggal_input AT TIME ZONE 'Asia/Jakarta') = %s
            ORDER BY e.tanggal_input
        """, (year, month))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def get_recent_logs():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                e.id,
                l.nama_lokasi,
                p.sku,
                e.upc,
                e.expired_date
            FROM expired_logs e
            LEFT JOIN products p ON p.upc::text = e.upc::text
            LEFT JOIN locations l ON l.id::text = e.lokasi::text
            ORDER BY e.tanggal_input DESC
            LIMIT 10
        """)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

# ================= MENU =================

def main_menu():
    keyboard = [
        [KeyboardButton("➕ Input Produk"), KeyboardButton("📄 Export Harian")],
        [KeyboardButton("📊 Rekap Bulanan CSV"), KeyboardButton("🗑 Hapus Item")],
        [KeyboardButton("🚨 Notifikasi Expired")],
        [KeyboardButton("ℹ️ Help")],
        [KeyboardButton("🏠 Menu Utama")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = user_exists(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Anda tidak terdaftar.")
        return
    await update.message.reply_text(
        f"Halo {user[0]} 👋\nSilakan pilih menu:",
        reply_markup=main_menu()
    )

async def menu_utama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🏠 Kembali ke Menu Utama.",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 MENU:\n"
        "➕ Input Produk\n"
        "📄 Export Harian\n"
        "📊 Rekap Bulanan CSV\n"
        "🗑 Hapus Item",
        reply_markup=main_menu()
    )

async def cancel_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Selesai.",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

# ================= INPUT FLOW =================

async def start_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    locations = get_locations()
    keyboard = [[InlineKeyboardButton(l[1], callback_data=f"lokasi_{l[0]}")] for l in locations]
    await update.message.reply_text("Pilih Lokasi:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_LOKASI

async def pilih_lokasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lokasi_id = query.data.split("_")[1]
    context.user_data["lokasi"] = lokasi_id

    telegram_id = update.effective_user.id
    user = get_user_by_telegram_id(telegram_id)

    if not user:
        await query.edit_message_text("❌ Anda tidak terdaftar.")
        return ConversationHandler.END

    username, nama, role, is_active = user

    if not is_active:
        await query.edit_message_text("❌ Akun Anda tidak aktif.")
        return ConversationHandler.END

    context.user_data["pic"] = nama
    context.user_data["role"] = role

    await query.edit_message_text(
        f"📍 Lokasi dipilih ✔️\n"
        f"👤 PIC: {nama}\n\n"
        "Ketik SKU / Nama / UPC:"
    )
    return CARI_PRODUK

async def cari_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = search_product(update.message.text.strip())
    if not results:
        await update.message.reply_text("Produk tidak ditemukan.")
        return CARI_PRODUK

    keyboard = [[InlineKeyboardButton(p["nama_produk"], callback_data=f"produk_{p['upc']}")] for p in results]
    context.user_data["last"] = results
    await update.message.reply_text("Pilih Produk:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_PRODUK

async def pilih_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    upc = query.data.split("_")[1]
    selected = next(p for p in context.user_data["last"] if p["upc"] == upc)
    context.user_data["produk"] = selected
    await query.edit_message_text("Masukkan tanggal expired (ddmmyy):")
    return INPUT_EXPIRED

async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        expired_obj = datetime.strptime(update.message.text, "%d%m%y").date()
    except ValueError:
        await update.message.reply_text("❌ Format salah. Gunakan ddmmyy (contoh: 030326 untuk 3 Maret 2026)")
        return INPUT_EXPIRED

    produk = context.user_data["produk"]
    lokasi_id = context.user_data["lokasi"]
    upc = produk["upc"]
    pic = context.user_data["pic"]

    # Cek duplikasi di database
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT tanggal_input, pic 
            FROM expired_logs 
            WHERE lokasi = %s AND upc = %s AND expired_date = %s
        """, (lokasi_id, upc, expired_obj))
        existing = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if existing:
        tgl_input, pic_lama = existing
        # Format tanggal_input agar lebih rapi (misal: 2026-03-03 14:30)
        tgl_str = tgl_input.strftime("%Y-%m-%d %H:%M") if tgl_input else "tidak diketahui"
        await update.message.reply_text(
            f"⚠️ Produk dengan UPC {upc} dan tanggal expired {expired_obj} "
            f"sudah pernah diinput di lokasi ini pada {tgl_str} oleh {pic_lama}.\n"
            "Tidak diperbolehkan input duplikat."
        )
        # Kembali ke menu tambah produk lagi
        keyboard = [
            [KeyboardButton("➕ Tambah Produk Lagi")],
            [KeyboardButton("❌ Selesai")]
        ]
        await update.message.reply_text(
            "Silakan pilih menu:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return TAMBAH_LAGI

    # Jika tidak ada duplikasi, simpan data
    save_expired(
        lokasi_id,
        upc,
        produk["nama_produk"],
        expired_obj,
        pic
    )

    keyboard = [
        [KeyboardButton("➕ Tambah Produk Lagi")],
        [KeyboardButton("❌ Selesai")]
    ]
    await update.message.reply_text(
        "✅ Data berhasil disimpan.\nTambah produk lagi?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TAMBAH_LAGI

async def tambah_produk_lagi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Lokasi tetap ✔️\nPIC: {context.user_data['pic']}\n\n"
        "Ketik SKU / Nama / UPC:"
    )
    return CARI_PRODUK

# ================= EXPORT HARIAN =================
async def export_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tz = pytz.timezone("Asia/Jakarta")
        today = datetime.now(tz).date()

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT 
                    l.nama_lokasi,
                    p.sku,
                    e.nama_produk,
                    e.upc,
                    e.expired_date,
                    e.pic,
                    e.tanggal_input
                FROM expired_logs e
                LEFT JOIN locations l ON l.id::text = e.lokasi::text
                LEFT JOIN products p ON p.upc::text = e.upc::text
                WHERE DATE(e.tanggal_input) = %s
                ORDER BY e.expired_date ASC
            """, (today,))
            data = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        if not data:
            await update.effective_message.reply_text("Tidak ada data input hari ini.")
            return

        filename = f"expired_{today}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("========================================================\n")
            f.write("       LAPORAN DAILY CEK PRODUK MENDEKATI EXPIRED\n")
            f.write("STORE        : HPM JEMBER\n")
            f.write("DEPT         : DAIRY & FROZEN\n")
            f.write(f"TANGGAL UPDATE : {today}\n")
            f.write("========================================================\n\n")

            for row in data:
                lokasi, sku, produk, upc, expired, pic, input_date = row
                if isinstance(expired, datetime):
                    expired = expired.date()
                selisih = (expired - today).days
                if selisih < 0:
                    status = "🔴 SUDAH EXPIRED"
                elif selisih == 0:
                    status = "🟠 EXPIRED HARI INI"
                elif selisih == 1:
                    status = "🟡 H-1"
                elif 2 <= selisih <= 7:
                    status = f"🔵 H-{selisih}"
                else:
                    status = "🟢 AMAN"

                f.write(f"Lokasi     : {lokasi or '-'}\n")
                f.write(f"SKU        : {sku or '-'}\n")
                f.write(f"Produk     : {produk or '-'}\n")
                f.write(f"UPC        : {upc or '-'}\n")
                f.write(f"Expired    : {expired} | {status}\n")
                f.write(f"PIC        : {pic or '-'}\n")
                if input_date:
                    f.write(f"Input Date : {input_date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("--------------------------------------------------------\n")

        with open(filename, "rb") as f:
            await update.effective_message.reply_document(document=f)
        os.remove(filename)

    except Exception as e:
        logger.error(f"Error di export_harian: {e}")
        await update.effective_message.reply_text(f"❌ Gagal export harian: {e}")

# ================= EXPORT BULANAN =================
async def export_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tz = pytz.timezone("Asia/Jakarta")
        now = datetime.now(tz)

        data = get_monthly_report(now.year, now.month)

        if not data:
            await update.effective_message.reply_text("Tidak ada data bulan ini.")
            return

        filename = f"rekap_{now.year}_{now.month}.csv"
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Lokasi",
                "SKU",
                "Produk",
                "UPC",
                "Expired",
                "Status",
                "PIC",
                "Tanggal Input"
            ])

            today = now.date()
            for row in data:
                lokasi, sku, produk, upc, expired, pic, input_date = row
                if isinstance(expired, datetime):
                    expired = expired.date()
                selisih = (expired - today).days
                if selisih < 0:
                    status = "🔴 SUDAH EXPIRED"
                elif selisih == 0:
                    status = "🟠 HARI INI"
                elif selisih == 1:
                    status = "🟡 H-1"
                elif 2 <= selisih <= 7:
                    status = f"🔵 H-{selisih}"
                else:
                    status = "🟢 AMAN"

                writer.writerow([
                    lokasi or "-",
                    sku or "-",
                    produk or "-",
                    upc or "-",
                    expired,
                    status,
                    pic or "-",
                    input_date.strftime('%Y-%m-%d %H:%M:%S') if input_date else "-"
                ])

        with open(filename, "rb") as f:
            await update.effective_message.reply_document(document=f)
        os.remove(filename)

    except Exception as e:
        logger.error(f"Error di export_bulanan: {e}")
        await update.effective_message.reply_text(f"❌ Gagal rekap bulanan: {e}")

async def hapus_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Hapus item dimulai oleh user {update.effective_user.id}")

    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menghapus item.")
        return

    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            # JOIN dengan products, gunakan COALESCE agar jika SKU null, tampilkan nama_produk
            cur.execute("""
                SELECT 
                    e.id, 
                    COALESCE(p.sku, e.nama_produk, 'SKU/Nama tidak diketahui') AS identifier,
                    e.expired_date
                FROM expired_logs e
                LEFT JOIN products p ON p.upc::text = e.upc::text
                WHERE e.expired_date < CURRENT_DATE   -- Hanya yang sudah lewat
                ORDER BY e.expired_date ASC
            """)
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        if not rows:
            await update.message.reply_text("✅ Tidak ada produk expired.")
            return

        keyboard = []
        for row in rows:
            # row = (id, identifier, expired_date)
            keyboard.append([
                InlineKeyboardButton(
                    f"{row[1]} - {row[2]}",
                    callback_data=f"hapus_{row[0]}"
                )
            ])

        await update.message.reply_text(
            "🗑 Pilih produk expired yang ingin dihapus:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error di hapus_item_start: {e}", exc_info=True)
        await update.message.reply_text("❌ Terjadi kesalahan. Silakan coba lagi nanti.")

async def hapus_konfirmasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.edit_message_text("❌ Anda tidak berhak melakukan ini.")
        return

    try:
        # Ambil dan validasi item_id
        data_parts = query.data.split('_')
        if len(data_parts) < 2 or not data_parts[1].isdigit():
            await query.edit_message_text("❌ ID produk tidak valid.")
            return
        item_id = data_parts[1]

        conn = get_connection()
        cur = conn.cursor()
        try:
            # Ambil detail produk (SKU atau nama_produk, dan expired_date)
            cur.execute("""
                SELECT 
                    COALESCE(p.sku, e.nama_produk, 'SKU/Nama tidak diketahui') AS identifier,
                    e.expired_date
                FROM expired_logs e
                LEFT JOIN products p ON p.upc::text = e.upc::text
                WHERE e.id = %s
            """, (item_id,))
            row = cur.fetchone()
        finally:
            cur.close()
            conn.close()

        if not row:
            await query.edit_message_text("❌ Data tidak ditemukan.")
            return

        identifier, expired = row

        keyboard = [[
            InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"confirmhapus_{item_id}"),
            InlineKeyboardButton("❌ Batal", callback_data="batalhapus")
        ]]

        await query.edit_message_text(
            f"📦 **DETAIL PRODUK**\n\n"
            f"SKU/Nama : {identifier}\n"
            f"Expired  : {expired}\n\n"
            f"Yakin ingin menghapus data ini?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error di hapus_konfirmasi: {e}", exc_info=True)
        await query.edit_message_text("❌ Terjadi kesalahan. Silakan coba lagi nanti.")

async def confirm_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.edit_message_text("❌ Anda tidak berhak melakukan ini.")
        return

    try:
        data_parts = query.data.split('_')
        if len(data_parts) < 2 or not data_parts[1].isdigit():
            await query.edit_message_text("❌ ID produk tidak valid.")
            return
        item_id = data_parts[1]

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM expired_logs WHERE id = %s", (item_id,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

        await query.edit_message_text("✅ Item berhasil dihapus.")
    except Exception as e:
        logger.error(f"Error di confirm_hapus: {e}", exc_info=True)
        await query.edit_message_text("❌ Gagal menghapus item.")

async def batal_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Penghapusan dibatalkan.")

async def invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Input tidak valid. Masukkan tanggal dalam format **ddmmyy** (contoh: 030326 untuk 3 Maret 2026) atau gunakan menu di bawah.",
        reply_markup=ReplyKeyboardMarkup([["❌ Selesai", "🏠 Menu Utama"]], resize_keyboard=True)

async def hapus_item_dari_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Akhiri percakapan
    await hapus_item_start(update, context)
    return ConversationHandler.END

# ================= NOTIFIKASI EXPIRED =================
async def notifikasi_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT 
                    l.nama_lokasi,
                    p.sku,
                    e.nama_produk,
                    e.upc,
                    e.expired_date,
                    e.pic
                FROM expired_logs e
                LEFT JOIN locations l ON l.id::text = e.lokasi::text
                LEFT JOIN products p ON p.upc::text = e.upc::text
                WHERE e.expired_date <= CURRENT_DATE + INTERVAL '1 day'
                ORDER BY e.expired_date ASC
            """)
            data = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        if not data:
            await update.message.reply_text("✅ Tidak ada produk expired / H-1.")
            return

        today = date.today()
        pesan = "🚨 *NOTIFIKASI PRODUK EXPIRED*\n\n"

        for row in data:
            lokasi, sku, produk, upc, expired, pic = row
            selisih = (expired - today).days

            if selisih < 0:
                status = "🔴 SUDAH EXPIRED"
            elif selisih == 0:
                status = "🟠 EXPIRED HARI INI"
            elif selisih == 1:
                status = "🟡 H-1"
            else:
                continue

            pesan += (
                f"📍 {lokasi or '-'}\n"
                f"SKU: {sku or '-'}\n"
                f"UPC: {upc or '-'}\n"
                f"Produk: {produk or '-'}\n"
                f"Expired: {expired} ({status})\n"
                f"PIC: {pic or '-'}\n"
                f"----------------------\n"
            )

        await update.message.reply_text(pesan)
    except Exception as e:
        logger.error(f"Error di notifikasi_expired: {e}")
        await update.message.reply_text("❌ Gagal mengambil notifikasi.")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Conversation Handler untuk Input Produk
   conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Text("➕ Input Produk"), start_input)
    ],
    states={
        PILIH_LOKASI: [CallbackQueryHandler(pilih_lokasi, pattern="^lokasi_")],
        CARI_PRODUK: [MessageHandler(filters.TEXT & ~filters.COMMAND, cari_produk)],
        PILIH_PRODUK: [CallbackQueryHandler(pilih_produk, pattern="^produk_")],
        INPUT_EXPIRED: [
            MessageHandler(filters.Regex(r'^\d{6}$'), input_expired)  # Hanya terima 6 digit angka
        ],
        TAMBAH_LAGI: [
            MessageHandler(filters.Text("➕ Tambah Produk Lagi"), tambah_produk_lagi),
            MessageHandler(filters.Text("❌ Selesai"), cancel_process)
        ],
    },
        fallbacks=[
        MessageHandler(filters.Text("❌ Selesai"), cancel_process),
        MessageHandler(filters.Text("🏠 Menu Utama"), menu_utama),
        MessageHandler(filters.Text("🗑 Hapus Item"), hapus_item_start),
        MessageHandler(filters.TEXT & ~filters.COMMAND, invalid_input)  # Tangani input lain yang tidak valid
    ],
    allow_reentry=True,
)

    # Handler perintah start
    app.add_handler(CommandHandler("start", start))

    # Conversation handler
    app.add_handler(conv_handler)

    # Handler untuk tombol utama (di luar percakapan)
    app.add_handler(MessageHandler(filters.Text("🗑 Hapus Item"), hapus_item_start))
    app.add_handler(MessageHandler(filters.Text("📄 Export Harian"), export_harian))
    app.add_handler(MessageHandler(filters.Text("📊 Rekap Bulanan CSV"), export_bulanan))
    app.add_handler(MessageHandler(filters.Text("ℹ️ Help"), help_menu))
    app.add_handler(MessageHandler(filters.Text("🏠 Menu Utama"), menu_utama))
    app.add_handler(MessageHandler(filters.Text("🚨 Notifikasi Expired"), notifikasi_expired))

    # Handler untuk callback query dari proses hapus
    app.add_handler(CallbackQueryHandler(hapus_konfirmasi, pattern="^hapus_"))
    app.add_handler(CallbackQueryHandler(confirm_hapus, pattern="^confirmhapus_"))
    app.add_handler(CallbackQueryHandler(batal_hapus, pattern="^batalhapus$"))

    logger.info("✅ BOT FINAL STABLE RUNNING")
    app.run_polling()

