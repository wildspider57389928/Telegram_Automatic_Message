import telebot
from flask import Flask, request

TOKEN = "8261971291:AAFR5XCC5VfvoOMwqAxWUNoLe4oG_BzOQbc"  # توکن بات تلگرام
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"  # URL سرویس Render

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# دستور /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "سلام! من بات شما هستم.")

# مسیر webhook
@app.route("/", methods=["POST"])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "ok"

if __name__ == "__main__":
    import requests
    # ست کردن webhook خودکار
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=10000)
