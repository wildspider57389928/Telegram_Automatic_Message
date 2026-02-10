from deep_translator import GoogleTranslator
import feedparser
from bs4 import BeautifulSoup
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask, request
import requests
import os

TOKEN = "8261971291:AAFR5XCC5VfvoOMwqAxWUNoLe4oG_BzOQbc"
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"
CHANNEL_ID = "@MBB_Software_Group"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

RSS_URL = "https://www.engadget.com/rss.xml"

translator = GoogleTranslator(source="en", target="fa")

IMAGES_DIR = "images"
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

user_news_cache = {}

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

def extract_metadata(categories):
    provider = next((c.split("|")[1] for c in categories if c.lower().startswith("provider_name|")), "Unknown")
    author = next((c.split("|")[1] for c in categories if c.lower().startswith("author_name|")), "Unknown")
    region = next((c.split("|")[1] for c in categories if c.lower().startswith("region|")), "Unknown")
    language = next((c.split("|")[1] for c in categories if c.lower().startswith("language|")), "Unknown")
    return provider, author, region, language

def get_latest_news(limit=10):
    feed = feedparser.parse(RSS_URL)
    news_list = []
    for entry in feed.entries:
        categories = [cat.term if hasattr(cat, "term") else str(cat) for cat in entry.get("tags", [])]

        title = entry.title if "title" in entry else "No Title"

        description = clean_html(entry.summary if "summary" in entry else "")
        description = remove_copyright(description)
        if len(description) > 4000:
            continue  # رد کردن خبرهای خیلی طولانی
        description = description[:3900]

        pub_date = entry.get("published", "Unknown")

        image_url = None
        if "media_content" in entry:
            for media in entry.media_content:
                if media.get("medium") == "image" and "url" in media:
                    image_url = media["url"]
                    break

        provider, author, region, language = extract_metadata(categories)

        news_list.append({
            "title": title,
            "description": description,
            "image": image_url,
            "categories": categories,
            "pub_date": pub_date,
            "publisher": provider,
            "author": author,
            "region": region,
            "language": language,
            "link": entry.link
        })

        if len(news_list) >= limit:
            break

    return news_list

footer_text = (
    "\n\n📌 برای دنبال کردن آخرین اخبار و مطالب دنیای تکنولوژی، کانال‌های ما را مشاهده کنید:\n\n"
    "💬 تلگرام:\n"
    "https://t.me/MBB_Software_Group\n"
    "https://t.me/hooshmalinovin\n\n"
    "🧮 محاسبه‌گر جامع مالی:\n"
    "ابزاری قدرتمند برای مدیریت و محاسبات مالی شخصی و حرفه‌ای شما\n"
    "https://myket.ir/app/org.MBB.ComprehensiveFinancialCalculator"
)

@bot.message_handler(func=lambda m: m.text == "Send news")
def send_news_list(message):
    news_list = get_latest_news()
    if not news_list:
        bot.send_message(message.chat.id, "No news found ❌")
        return

    user_news_cache[message.chat.id] = news_list

    for idx, news in enumerate(news_list):
        category_lines = "\n- ".join([c for c in news["categories"] if not any(x in c.lower() for x in ["region|", "language|", "provider_name", "author_name"])])
        category_text = f"- {category_lines}" if category_lines else "No categories"

        text = (
            f"📢 {news['title']}\n"
            f"🗓 {news['pub_date']}\n\n"
            f"📂 Categories:\n{category_text}\n\n"
            f"🏷 Publisher: {news['publisher']}\n"
            f"✍ Author: {news['author']}\n"
            f"🌍 Region: {news['region']}\n"
            f"🈸 Language: {news['language']}\n\n"
        )

        preview_text = news["description"][:200] + "..." if len(news["description"]) > 200 else news["description"]
        text += preview_text

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📤 Send to Channel", callback_data=f"send_{idx}"))
        bot.send_message(message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_"))
def send_selected_news(call: CallbackQuery):
    idx = int(call.data.split("_")[1])
    news_list = user_news_cache.get(call.message.chat.id)

    if not news_list or idx >= len(news_list):
        bot.answer_callback_query(call.id, "News not found ❌")
        return

    news = news_list[idx]
    title_fa = translator.translate(news["title"])
    description_fa = translator.translate(news["description"])
    short_caption = f"📢 {title_fa[:100]}..."

    if news["image"]:
        image_path = os.path.join(IMAGES_DIR, "latest.jpg")
        download_image(news["image"], image_path)
        with open(image_path, "rb") as photo:
            bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=short_caption)
    else:
        bot.send_message(chat_id=CHANNEL_ID, text=short_caption)

    bot.send_message(chat_id=CHANNEL_ID, text=description_fa + footer_text)
    bot.answer_callback_query(call.id, "News sent to channel ✅")

@app.route("/", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "ok"

if __name__ == "__main__":
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
