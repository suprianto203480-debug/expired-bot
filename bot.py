import os
import psycopg2
import csv
import io
import pytz
from datetime import datetime, date, time
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile
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

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GROUP_ID = int(os.getenv("GROUP_ID"))  # isi di Railway

PILIH_LOKASI, PILIH_PIC, CARI_PRODUK, PILIH_PRODUK, INPUT_EXPIRED = range(5)

# ================= DATABASE =================

def db():
    return psycopg2.connect(DATABASE_URL)

def get_locations():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,nama_lokasi FROM locations WHERE is_active=true ORDER BY id")
            return cur.fetchall()

def get_users():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,nama FROM users WHERE is_active=true ORDER BY nama")
            return cur.fetchall()

def search_product(keyword):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT upc,sku,deskripsi
                FROM products
                WHERE upc ILIKE %s OR sku::text ILIKE %s OR deskripsi ILIKE %s
                LIMIT 10
            """,(f"%{keyword}%",f"%{keyword}%",f"%{keyword}%"))
            rows=cur.fetchall()
    return [{"upc":r[0],"sku":r[1],"nama":r[2]} for r in rows]

def save_expired(lokasi,upc,nama,expired,pic):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO expired_logs
                (tanggal_input,lokasi,upc,nama_produk,expired_date,pic)
                VALUES (NOW(),%s,%s,%s,%s,%s)
            """,(lokasi,upc,nama,expired,pic))
            conn.commit()

# ================= MENU =================

def menu():
    keyboard=[
        [KeyboardButton("➕ Input Produk"),KeyboardButton("🔄 Pindah Lokasi")],
        [KeyboardButton("📄 Export Harian"),KeyboardButton("📊 Rekap Bulanan CSV")],
        [KeyboardButton("ℹ️ Help"),KeyboardButton("❌ Batal")]
    ]
    return ReplyKeyboardMarkup(keyboard,resize_keyboard=True)

# ================= START =================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pilih Menu:",reply_markup=menu())

async def help_menu(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 MENU:\n"
        "➕ Input Produk\n"
        "🔄 Pindah Lokasi\n"
        "📄 Export Harian\n"
        "📊 Rekap Bulanan CSV\n"
        "❌ Batal",
        reply_markup=menu()
    )

async def cancel(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Dibatalkan",reply_markup=menu())
    return ConversationHandler.END

# ================= INPUT FLOW =================

async def start_input(update:Update,context:ContextTypes.DEFAULT_TYPE):
    keyboard=[[InlineKeyboardButton(l[1],callback_data=f"lok_{l[0]}")] for l in get_locations()]
    await update.message.reply_text("Pilih Lokasi:",reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_LOKASI

async def pilih_lokasi(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    context.user_data["lokasi"]=q.data.split("_")[1]
    keyboard=[[InlineKeyboardButton(u[1],callback_data=f"pic_{u[0]}")] for u in get_users()]
    await q.edit_message_text("Pilih PIC:",reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_PIC

async def pilih_pic(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    context.user_data["pic"]=q.data.split("_")[1]
    await q.edit_message_text("Ketik SKU / Nama / UPC:")
    return CARI_PRODUK

async def cari_produk(update:Update,context:ContextTypes.DEFAULT_TYPE):
    hasil=search_product(update.message.text)
    if not hasil:
        await update.message.reply_text("Produk tidak ditemukan.")
        return CARI_PRODUK
    context.user_data["hasil"]=hasil
    keyboard=[[InlineKeyboardButton(h["nama"],callback_data=f"prd_{h['upc']}")] for h in hasil]
    await update.message.reply_text("Pilih Produk:",reply_markup=InlineKeyboardMarkup(keyboard))
    return PILIH_PRODUK

async def pilih_produk(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    upc=q.data.split("_")[1]
    p=next(h for h in context.user_data["hasil"] if h["upc"]==upc)
    context.user_data["produk"]=p
    await q.edit_message_text("Masukkan tanggal expired (YYYY-MM-DD):")
    return INPUT_EXPIRED

async def input_expired(update:Update,context:ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text,"%Y-%m-%d")
    except:
        await update.message.reply_text("Format salah.")
        return INPUT_EXPIRED

    p=context.user_data["produk"]
    save_expired(
        context.user_data["lokasi"],
        p["upc"],
        p["nama"],
        update.message.text,
        context.user_data["pic"]
    )

    await update.message.reply_text("✅ Data tersimpan.",reply_markup=menu())
    return ConversationHandler.END

# ================= EXPORT HARIAN =================

async def export_harian(update:Update,context:ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id,lokasi,upc,nama_produk,expired_date,pic
                FROM expired_logs
                WHERE DATE(tanggal_input)=CURRENT_DATE
                ORDER BY lokasi,upc
            """)
            rows=cur.fetchall()

    if not rows:
        await update.message.reply_text("Tidak ada data hari ini.")
        return

    today=datetime.now().strftime("%Y-%m-%d")
    filename=f"expired_{today}.txt"
    lines=[f"LAPORAN EXPIRED - {today}","="*40]

    for r in rows:
        selisih=(r[4]-date.today()).days
        status="SUDAH EXPIRED" if selisih<=0 else f"H-{selisih}"
        lines+= [
            f"Lokasi : {r[1]}",
            f"UPC    : {r[2]}",
            f"Produk : {r[3]}",
            f"Expired: {r[4]} ({status})",
            f"PIC    : {r[5]}",
            "-"*40
        ]

    with open(filename,"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

    with open(filename,"rb") as f:
        await update.message.reply_document(f)

    os.remove(filename)

# ================= REKAP BULANAN CSV =================

async def export_bulanan(update:Update,context:ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT lokasi,upc,nama_produk,expired_date,pic,tanggal_input
                FROM expired_logs
                ORDER BY tanggal_input
            """)
            rows=cur.fetchall()

    if not rows:
        await update.message.reply_text("Tidak ada data.")
        return

    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(["Lokasi","UPC","Produk","Expired","Status","PIC","Tanggal Input"])

    today=date.today()

    for r in rows:
        selisih=(r[3]-today).days
        if selisih>0:
            status=f"H-{selisih}"
        elif selisih==0:
            status="EXPIRED HARI INI"
        else:
            status=f"SUDAH EXPIRED {abs(selisih)} HARI"

        writer.writerow([r[0],r[1],r[2],r[3],status,r[4],r[5]])

    output.seek(0)
    await update.message.reply_document(
        document=InputFile(io.BytesIO(output.getvalue().encode()),filename="rekap_bulanan.csv")
    )

# ================= AUTO NOTIF 06:00 WIB =================

async def morning_report(context:ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT nama_produk,lokasi,expired_date FROM expired_logs")
            rows=cur.fetchall()

    today=date.today()
    message="📢 MONITORING EXPIRED\n\n"
    found=False

    for r in rows:
        selisih=(r[2]-today).days
        if selisih in [5,4,3,2,1]:
            message+=f"⚠ H-{selisih} | {r[0]} | {r[1]} | {r[2]}\n"
            found=True
        elif selisih<=0:
            message+=f"🚨 EXPIRED | {r[0]} | {r[1]} | {r[2]}\n"
            found=True

    if not found:
        message="✅ Tidak ada item H-5 s/d expired."

    await context.bot.send_message(chat_id=GROUP_ID,text=message)

# ================= MAIN =================

if __name__=="__main__":
    app=ApplicationBuilder().token(TOKEN).build()

    conv=ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(➕ Input Produk|🔄 Pindah Lokasi)$"),start_input)],
        states={
            PILIH_LOKASI:[CallbackQueryHandler(pilih_lokasi,pattern="^lok_")],
            PILIH_PIC:[CallbackQueryHandler(pilih_pic,pattern="^pic_")],
            CARI_PRODUK:[MessageHandler(filters.TEXT & ~filters.COMMAND,cari_produk)],
            PILIH_PRODUK:[CallbackQueryHandler(pilih_produk,pattern="^prd_")],
            INPUT_EXPIRED:[MessageHandler(filters.TEXT & ~filters.COMMAND,input_expired)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Batal$"),cancel)]
    )

    app.add_handler(CommandHandler("start",start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^📄 Export Harian$"),export_harian))
    app.add_handler(MessageHandler(filters.Regex("^📊 Rekap Bulanan CSV$"),export_bulanan))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"),help_menu))

    tz=pytz.timezone("Asia/Jakarta")
    app.job_queue.run_daily(morning_report,time=time(6,0,tzinfo=tz))

    print("✅ BOT FINAL RUNNING")
    app.run_polling()
