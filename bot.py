import os
import psycopg2
import csv
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

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

PILIH_LOKASI, PILIH_PIC, CARI_PRODUK, PILIH_PRODUK, INPUT_EXPIRED, TAMBAH_LAGI = range(6)

# ================= DATABASE =================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def user_exists(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nama FROM users WHERE telegram_id=%s AND is_active=true", (telegram_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def get_locations():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id,nama_lokasi FROM locations WHERE is_active=true ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_active_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id,nama FROM users WHERE is_active=true ORDER BY nama")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def search_product(keyword):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT upc, sku, deskripsi
        FROM products
        WHERE upc ILIKE %s OR sku::text ILIKE %s OR deskripsi ILIKE %s
        LIMIT 10
    """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"upc": r[0], "sku": r[1], "nama_produk": r[2]} for r in rows]

def save_expired(lokasi_id, upc, nama_produk, expired_date, pic):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expired_logs
        (tanggal_input,lokasi,upc,nama_produk,expired_date,pic)
        VALUES ((NOW() AT TIME ZONE 'Asia/Jakarta'),%s,%s,%s,%s,%s)
    """,(lokasi_id,upc,nama_produk,expired_date,pic))
    conn.commit()
    cur.close()
    conn.close()

def get_today_expired():
    conn = get_connection()
    cur = conn.cursor()
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
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_monthly_report(year,month):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.nama_lokasi,p.sku,e.nama_produk,
               e.upc,e.expired_date,e.pic,e.tanggal_input
        FROM expired_logs e
        LEFT JOIN locations l ON l.id::text=e.lokasi::text
        LEFT JOIN products p ON p.upc::text=e.upc::text
        WHERE EXTRACT(YEAR FROM e.tanggal_input)=%s
        AND EXTRACT(MONTH FROM e.tanggal_input)=%s
        ORDER BY e.tanggal_input
    """,(year,month))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_recent_logs():
    conn = get_connection()
    cur = conn.cursor()
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
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ================= MENU =================

def main_menu():
    keyboard = [
        [KeyboardButton("➕ Input Produk"), KeyboardButton("📄 Export Harian")],
        [KeyboardButton("📊 Rekap Bulanan CSV"), KeyboardButton("🗑 Hapus Item")],
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
    context.user_data["lokasi"] = query.data.split("_")[1]

    users = get_active_users()
    keyboard = [[InlineKeyboardButton(u[1], callback_data=f"pic_{u[0]}")] for u in users]
    await query.edit_message_text("Pilih PIC:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_PIC

async def pilih_pic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pic_id = query.data.split("_")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nama FROM users WHERE id=%s",(pic_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    context.user_data["pic"] = result[0]
    await query.edit_message_text(f"PIC: {result[0]}\n\nKetik SKU / Nama / UPC:")
    return CARI_PRODUK

async def cari_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = search_product(update.message.text.strip())
    if not results:
        await update.message.reply_text("Produk tidak ditemukan.")
        return CARI_PRODUK

    keyboard = [[InlineKeyboardButton(p["nama_produk"],callback_data=f"produk_{p['upc']}")] for p in results]
    context.user_data["last"] = results
    await update.message.reply_text("Pilih Produk:",reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_PRODUK

async def pilih_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    upc = query.data.split("_")[1]
    selected = next(p for p in context.user_data["last"] if p["upc"]==upc)
    context.user_data["produk"]=selected
    await query.edit_message_text("Masukkan tanggal expired (ddmmyy):")
    return INPUT_EXPIRED

async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        expired_obj = datetime.strptime(update.message.text, "%d%m%y").date()
    except:
        await update.message.reply_text("Format salah. Gunakan ddmmyy")
        return INPUT_EXPIRED

    p = context.user_data["produk"]

    save_expired(
        context.user_data["lokasi"],
        p["upc"],
        p["nama_produk"],
        expired_obj,
        context.user_data["pic"]
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
            WHERE DATE(e.tanggal_input AT TIME ZONE 'Asia/Jakarta') = %s
            ORDER BY e.expired_date ASC
        """, (today,))

        data = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    if not data:
        await update.message.reply_text("Tidak ada data input hari ini.")
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

            # Pastikan expired adalah date
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
        await update.message.reply_document(document=f)

    os.remove(filename)
# ================= EXPORT BULANAN =================
async def export_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    tz = pytz.timezone("Asia/Jakarta")
    now = datetime.now(tz)

    data = get_monthly_report(now.year, now.month)

    if not data:
        await update.message.reply_text("Tidak ada data bulan ini.")
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
        await update.message.reply_document(document=f)

    os.remove(filename)
# ================= HAPUS =================

async def hapus_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_recent_logs()
    if not data:
        await update.message.reply_text("Tidak ada data untuk dihapus.")
        return

    keyboard = []

    for row in data:
        id_, lokasi, sku, upc, expired = row

        selisih = (expired - date.today()).days

        if selisih < 0:
            status = "🔴 EXPIRED"
        elif selisih == 0:
            status = "🟠 HARI INI"
        elif selisih == 1:
            status = "🟡 H-1"
        elif 2 <= selisih <= 7:
            status = f"🔵 H-{selisih}"
        else:
            status = "🟢 AMAN"

        keyboard.append([
            InlineKeyboardButton(
                f"{lokasi} - {sku} - {upc} - {expired} - {status}",
                callback_data=f"hapus_{id_}"
            )
        ])

    await update.message.reply_text(
        "🗑 Pilih item yang ingin dihapus:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def hapus_konfirmasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_id = query.data.split("_")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.nama_lokasi, p.sku, e.upc, e.nama_produk, e.expired_date, e.pic
        FROM expired_logs e
        LEFT JOIN products p ON p.upc::text = e.upc::text
        LEFT JOIN locations l ON l.id::text = e.lokasi::text
        WHERE e.id=%s
    """, (item_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        await query.edit_message_text("Data tidak ditemukan.")
        return

    lokasi, sku, upc, produk, expired, pic = row

    keyboard = [
        [
            InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"confirmhapus_{item_id}"),
            InlineKeyboardButton("❌ Batal", callback_data="batalhapus")
        ]
    ]

    await query.edit_message_text(
        f"""📦 DETAIL PRODUK

Lokasi   : {lokasi}
SKU      : {sku}
UPC      : {upc}
Produk   : {produk}
Expired  : {expired}
PIC      : {pic}

Yakin ingin menghapus data ini?""",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def confirm_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_id = query.data.split("_")[1]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expired_logs WHERE id=%s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()

    await query.edit_message_text("✅ Item berhasil dihapus.")
async def batal_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("❌ Penghapusan dibatalkan.")

# ================= MAIN =================

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Input Produk$"), start_input)
        ],
        states={
            PILIH_LOKASI: [CallbackQueryHandler(pilih_lokasi, pattern="^lokasi_")],
            PILIH_PIC: [CallbackQueryHandler(pilih_pic, pattern="^pic_")],
            CARI_PRODUK: [MessageHandler(filters.TEXT & ~filters.COMMAND, cari_produk)],
            PILIH_PRODUK: [CallbackQueryHandler(pilih_produk, pattern="^produk_")],
            INPUT_EXPIRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_expired)],
            TAMBAH_LAGI: [
                MessageHandler(filters.Regex("^➕ Tambah Produk Lagi$"), tambah_produk_lagi),
                MessageHandler(filters.Regex("^❌ Selesai$"), cancel_process)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Selesai$"), cancel_process),
            MessageHandler(filters.Regex("^🏠 Menu Utama$"), menu_utama)
        ],
        allow_reentry=True
    )

    # ===== CALLBACK HANDLER DITARUH DI ATAS =====
    app.add_handler(CallbackQueryHandler(hapus_konfirmasi, pattern="^hapus_"))
    app.add_handler(CallbackQueryHandler(confirm_hapus, pattern="^confirmhapus_"))
    app.add_handler(CallbackQueryHandler(batal_hapus, pattern="^batalhapus$"))

    # ===== COMMAND & MENU =====
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    app.add_handler(MessageHandler(filters.Regex("^📄 Export Harian$"), export_harian))
    app.add_handler(MessageHandler(filters.Regex("^📊 Rekap Bulanan CSV$"), export_bulanan))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Hapus Item$"), hapus_item_start))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"), help_menu))
    app.add_handler(MessageHandler(filters.Regex("^🏠 Menu Utama$"), menu_utama))

    print("✅ BOT FINAL STABLE RUNNING")
    app.run_polling()
