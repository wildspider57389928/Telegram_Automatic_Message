from deep_translator import GoogleTranslator
import feedparser
from bs4 import BeautifulSoup
import telebot
from flask import Flask, request
import requests
import os

# توکن تست
TOKEN = "8261971291:AAFR5XCC5VfvoOMwqAxWUNoLe4oG_BzOQbc"
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"
CHANNEL_ID = "@MBB_Software_Group"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

ALLOWED_CATEGORIES = ["Software", "Technology & Electronics", "Video Games"]
RSS_URL = "https://www.engadget.com/rss.xml"

translator = GoogleTranslator(source='en', target='fa')

IMAGES_DIR = "images"
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)


def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text().strip()

def remove_copyright(text):
    markers = ["This article originally appeared on Engadget", "Read more at Engadget"]
    for marker in markers:
        if marker in text:
            text = text.split(marker)[0].strip()
    return text

def download_image(url, filename):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(filename, "wb") as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

def get_latest_news():
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        categories = [cat.term if hasattr(cat, 'term') else cat for cat in entry.get('tags', [])]
        if not any(cat in ALLOWED_CATEGORIES for cat in categories):
            continue

        title = entry.title if 'title' in entry else "No Title"
        description = clean_html(entry.summary if 'summary' in entry else "")
        description = remove_copyright(description)
        if len(description) > 4000:
            continue

        image_url = None
        if 'media_content' in entry and len(entry.media_content) > 0:
            image_url = entry.media_content[0].get("url")

        return {"title": title, "description": description, "image": image_url}
    return None

@bot.message_handler(func=lambda m: m.text == "Send news")
def send_one_news(message):
    bot.send_chat_action(message.chat.id, 'typing')

    news = get_latest_news()
    if not news:
        bot.send_message(message.chat.id, "هیچ خبری یافت نشد ❌")
        return

    title_fa = translator.translate(news['title'])
    description_fa = translator.translate(news['description'])
    short_caption = f"📢 {title_fa[:100]}..."  # کپشن کوتاه برای عکس

    if news["image"]:
        image_path = os.path.join(IMAGES_DIR, "latest.jpg")
        if download_image(news["image"], image_path):
            with open(image_path, "rb") as photo:
                bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=short_caption)
        else:
            bot.send_message(chat_id=CHANNEL_ID, text=short_caption)
    else:
        bot.send_message(chat_id=CHANNEL_ID, text=short_caption)

    # متن کامل جدا
    bot.send_message(chat_id=CHANNEL_ID, text=description_fa)
    bot.send_message(message.chat.id, "خبر به چنل ارسال شد ✅")

@app.route("/", methods=["POST"])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "ok"

if __name__ == "__main__":
    # ست کردن webhook فقط یکبار کافی است
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
