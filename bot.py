import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===================== KONFIGURASI =====================
TOKEN = os.getenv("TOKEN")  # Pastikan TOKEN ada di Railway Variables

# ===================== START COMMAND =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [KeyboardButton(
            text="📷 Scan Item",
            web_app=WebAppInfo(
                url="https://ISI_URL_WEBAPP_NANTI"
            )
        )]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "Silakan klik tombol Scan Item untuk mulai.",
        reply_markup=reply_markup
    )

# ===================== MAIN =====================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
