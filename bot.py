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
        VALUES (NOW(),%s,%s,%s,%s,%s)
    """,(lokasi_id,upc,nama_produk,expired_date,pic))
    conn.commit()
    cur.close()
    conn.close()

def get_today_expired():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.nama_lokasi,p.sku,e.nama_produk,
               e.upc,e.expired_date,e.pic
        FROM expired_logs e
        LEFT JOIN locations l ON l.id::text=e.lokasi::text
        LEFT JOIN products p ON p.upc::text=e.upc::text
        WHERE DATE(e.tanggal_input)=CURRENT_DATE
        ORDER BY l.nama_lokasi,p.sku
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

# ================= MENU =================

def main_menu():
    keyboard = [
        [KeyboardButton("➕ Input Produk"), KeyboardButton("📄 Export Harian")],
        [KeyboardButton("📊 Rekap Bulanan CSV"), KeyboardButton("ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_exists(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Anda tidak terdaftar.")
        return
    await update.message.reply_text(
        f"Halo {user[0]} 👋\nSilakan pilih menu:",
        reply_markup=main_menu()
    )

async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 MENU:\n"
        "➕ Input Produk\n"
        "📄 Export Harian\n"
        "📊 Rekap Bulanan CSV",
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
    await query.edit_message_text("Masukkan tanggal expired (YYYY-MM-DD):")
    return INPUT_EXPIRED

async def input_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text,"%Y-%m-%d")
    except:
        await update.message.reply_text("Format salah. Gunakan YYYY-MM-DD")
        return INPUT_EXPIRED

    p = context.user_data["produk"]

    save_expired(
        context.user_data["lokasi"],
        p["upc"],
        p["nama_produk"],
        update.message.text,
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

# ================= EXPORT =================

async def export_harian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_today_expired()
    if not data:
        await update.message.reply_text("Tidak ada data hari ini.")
        return

    today=datetime.now().strftime("%Y-%m-%d")
    filename=f"expired_{today}.txt"

    lines=[f"LAPORAN EXPIRED - {today}","="*50]

    for row in data:
        lokasi,sku,produk,upc,expired,pic=row
        selisih=(expired-date.today()).days
        status=""
        if selisih<0: status="⚠️ SUDAH EXPIRED"
        elif selisih<=3: status="⚠️ SEGERA EXPIRED"

        lines+= [
            f"Lokasi : {lokasi}",
            f"SKU    : {sku}",
            f"Produk : {produk}",
            f"UPC    : {upc}",
            f"Expired: {expired} {status}",
            f"PIC    : {pic}",
            "-"*50
        ]

    with open(filename,"w",encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(filename,"rb") as f:
        await update.message.reply_document(f)
    os.remove(filename)

async def export_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now=datetime.now()
    data=get_monthly_report(now.year,now.month)
    if not data:
        await update.message.reply_text("Tidak ada data bulan ini.")
        return

    filename=f"rekap_{now.year}_{now.month}.csv"
    with open(filename,"w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f)
        writer.writerow(["Lokasi","SKU","Produk","UPC","Expired","PIC","Tanggal Input"])
        writer.writerows(data)

    with open(filename,"rb") as f:
        await update.message.reply_document(f)
    os.remove(filename)

# ================= MAIN =================

if __name__=="__main__":
    app=ApplicationBuilder().token(TOKEN).build()

    conv=ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Input Produk$"), start_input)
        ],
        states={
            PILIH_LOKASI:[CallbackQueryHandler(pilih_lokasi,pattern="^lokasi_")],
            PILIH_PIC:[CallbackQueryHandler(pilih_pic,pattern="^pic_")],
            CARI_PRODUK:[MessageHandler(filters.TEXT & ~filters.COMMAND,cari_produk)],
            PILIH_PRODUK:[CallbackQueryHandler(pilih_produk,pattern="^produk_")],
            INPUT_EXPIRED:[MessageHandler(filters.TEXT & ~filters.COMMAND,input_expired)],
            TAMBAH_LAGI:[
                MessageHandler(filters.Regex("^➕ Tambah Produk Lagi$"), tambah_produk_lagi),
                MessageHandler(filters.Regex("^❌ Selesai$"), cancel_process)
            ]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Selesai$"), cancel_process)]
    )

    app.add_handler(CommandHandler("start",start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^📄 Export Harian$"),export_harian))
    app.add_handler(MessageHandler(filters.Regex("^📊 Rekap Bulanan CSV$"),export_bulanan))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"),help_menu))

    print("✅ BOT FINAL STABLE RUNNING")
    app.run_polling()
