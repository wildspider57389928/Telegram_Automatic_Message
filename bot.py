from deep_translator import GoogleTranslator
import feedparser
from bs4 import BeautifulSoup
import telebot
from flask import Flask, request
import time

TOKEN = "8261971291:AAFR5XCC5VfvoOMwqAxWUNoLe4oG_BzOQbc"
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"
CHANNEL_ID = "@MBB_Software_Group"  # یا ID چنل مثل -100xxxxxxxxxx

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

ALLOWED_CATEGORIES = ["Software", "Technology & Electronics", "Video Games"]
RSS_URL = "https://www.engadget.com/rss.xml"

translator = GoogleTranslator(source='en', target='fa')

# ============ توابع پردازش خبر ============
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

def get_latest_news():
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        categories = [cat.term if hasattr(cat, 'term') else cat for cat in entry.get('tags', [])]
        if not any(cat in ALLOWED_CATEGORIES for cat in categories):
            continue

        title = entry.title if 'title' in entry else "No Title"
        description = clean_html(entry.summary if 'summary' in entry else "No Description")
        description = remove_copyright(description)
        if len(description) > 2000:
            continue

        image_url = None
        if 'media_content' in entry:
            image_url = entry.media_content[0]['url'] if len(entry.media_content) > 0 else None

        return {"title": title, "description": description, "image": image_url}
    return None

# ============ بات تلگرام ============
@bot.message_handler(func=lambda m: m.text == "Send news")
def send_one_news(message):
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(0.5)
    news = get_latest_news()
    if news:
        # ترجمه عنوان و توضیحات
        title_fa = translator.translate(news['title'])
        description_fa = translator.translate(news['description'])
        msg = f"📢 *{title_fa}*\n\n{description_fa}"
        bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode='Markdown')
        bot.send_message(message.chat.id, "خبر به چنل ارسال شد ✅")
    else:
        bot.send_message(message.chat.id, "هیچ خبری یافت نشد ❌")

# ============ وبهوک ============
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
