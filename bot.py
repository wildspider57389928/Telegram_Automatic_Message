from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask, request
import os

TOKEN =  os.getenv("BOT_TOKEN")# توکن بات تلگرام رو اینجا بزار
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"  # URL سرویس Render

app = Flask(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من بات شما هستم.")

application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))

@app.route("/", methods=["POST"])
def webhook():
    application.process_update(Update.de_json(request.get_json(force=True), application.bot))
    return "ok"

if __name__ == "__main__":
    import requests
    # ست کردن webhook خودکار
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=10000)
