from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8590161595:AAFmbvT-yD_qPPuJ8Yb7glYFehmIy26BtqA"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Monitoring Expired Aktif ✅")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

if __name__ == "__main__":
    print("Bot sedang berjalan...")
    app.run_polling()
