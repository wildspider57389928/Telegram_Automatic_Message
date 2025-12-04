import telebot
from flask import Flask, request

TOKEN = "8254210385:AAEXPb10qF5U2c7uXV2tvBO8SeRQZzcB4Mc"
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("🛍️ انتخاب محصول")
    btn2 = telebot.types.KeyboardButton("📦 محصولات خریداری‌شده")
    btn3 = telebot.types.KeyboardButton("☎️ پشتیبانی")
    keyboard.add(btn1, btn2, btn3)
    bot.send_message(message.chat.id, "سلام! من ربات شما هستم.", reply_markup=keyboard)

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    if message.text == "🛍️ انتخاب محصول":
        bot.send_message(message.chat.id, "لطفاً محصول مورد نظر خود را انتخاب کنید.")
    elif message.text == "📦 محصولات خریداری‌شده":
        bot.send_message(message.chat.id, "لیست خریدهای شما در این بخش نمایش داده می‌شود.")
    elif message.text == "☎️ پشتیبانی":
        bot.send_message(message.chat.id, "برای ارتباط با پشتیبانی پیام خود را ارسال کنید.")

@app.route("/", methods=["POST"])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "ok"

if __name__ == "__main__":
    import requests
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=10000)
