from deep_translator import GoogleTranslator
import feedparser
from bs4 import BeautifulSoup
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from flask import Flask, request
import requests
import os
from google import genai

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://telegram-automatic-message.onrender.com/"
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

BALE_TOKEN = os.getenv("BALE_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

RSS_URL = "https://www.engadget.com/rss.xml"

translator = GoogleTranslator(source="en", target="fa")
client = genai.Client(api_key=GEMINI_API_KEY)

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

def analyze_news_with_gemini(description):
    prompt = f"""
    تو یک خبرنگار حرفه‌ای هستی. متن طولانی خبری زیر را به یک خبر کوتاه و مفید در ۳ تا ۴ پاراگراف تبدیل کن.

قوانین:
پاراگراف اول: شامل چه کسی، چه اتفاقی، کجا، کی (Who, What, Where, When) همراه با مهمترین عدد یا آمار.

پاراگراف دوم: جزئیات تکمیلی و چرایی اصلی رویداد (Why).

پاراگراف سوم (و در صورت نیاز چهارم): پیامد فوری، واکنش مسئول یا تأثیر خبر.

سبک: خشک، بی‌طرف، روان و ساده. حذف نقل قول مستقیم و توضیحات اضافی. هیچ قسمتی از متن را بولد یا پررنگ نکن. طول کل حداکثر ۱۰۰ کلمه.
متن خبر:
{description}
"""
    try:
        response = client.models.generate_content(model="gemini-2.5-flash",contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"خطا در تحلیل خبر:{e}"

def get_latest_news(limit=10):
    feed = feedparser.parse(RSS_URL)
    news_list = []
    for entry in feed.entries:
        title = entry.title if "title" in entry else "No Title"
        description = clean_html(entry.summary if "summary" in entry else "")
        description = remove_copyright(description)
        if len(description) > 4000:
            continue
        description = description[:3900]
        pub_date = entry.get("published", "Unknown")

        image_url = None
        if "media_content" in entry:
            for media in entry.media_content:
                if media.get("medium") == "image" and "url" in media:
                    image_url = media["url"]
                    break

        news_list.append({"title": title,"description": description,"image": image_url,"pub_date": pub_date,"link": entry.link})
        if len(news_list) >= limit:
            break
    return news_list
    
def send_to_bale(text,image_path=None):
    try:
        if image_path:
            url=f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendPhoto"
            with open(image_path,"rb") as photo:
                r=requests.post(url,data={"chat_id":BALE_CHAT_ID},files={"photo":photo})
                print("Bale photo:",r.text)
        url=f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
        r=requests.post(url,data={"chat_id":BALE_CHAT_ID,"text":text})
        print("Bale message:",r.text)

    except Exception as e:
        print("Bale error:",e)
        
footer_text = """
\n📌 برای دنبال کردن آخرین اخبار و مطالب دنیای تکنولوژی و هوش مصنوعی، کانال‌های ما را مشاهده کنید:

💬 تلگرام:
https://t.me/MBB_Software_Group
https://t.me/hooshmalinovin

📱 بله:
https://ble.ir/MBB_Software_Group
"""

@bot.message_handler(func=lambda m: m.text and m.text.lower()=="send telegram")
def send_news_list(message):
    news_list=get_latest_news()
    if not news_list:
        bot.send_message(message.chat.id,"No news found ❌")
        return
    user_news_cache[message.chat.id]=news_list
    for idx,news in enumerate(news_list):
        preview=news["description"][:200]+"..."
        text=f"📢 {news['title']}\n🗓 {news['pub_date']}\n\n{preview}"
        keyboard=InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📤 Send to Channel",callback_data=f"send_{idx}"))
        bot.send_message(message.chat.id,text,reply_markup=keyboard)

@bot.message_handler(func=lambda m: m.text and m.text.lower()=="send bale")
def send_bale_list(message):
    news_list=get_latest_news()
    if not news_list:
        bot.send_message(message.chat.id,"No news found ❌")
        return
    user_news_cache[message.chat.id]=news_list
    for idx,news in enumerate(news_list):
        preview=news["description"][:200]+"..."
        text=f"📢 {news['title']}\n🗓 {news['pub_date']}\n\n{preview}"
        keyboard=InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📤 Send to Bale",callback_data=f"bale_{idx}"))
        bot.send_message(message.chat.id,text,reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_"))
def send_selected_news(call: CallbackQuery):
    idx=int(call.data.split("_")[1])
    news_list=user_news_cache.get(call.message.chat.id)
    if not news_list or idx>=len(news_list):
        bot.answer_callback_query(call.id,"News not found ❌")
        return
    news=news_list[idx]
    title_fa=translator.translate(news["title"])
    analysis_text=analyze_news_with_gemini(news["description"])
    caption=f"📢 {title_fa}"
    if news["image"]:
        image_path=os.path.join(IMAGES_DIR,"latest.jpg")
        download_image(news["image"],image_path)
        with open(image_path,"rb") as photo:
            bot.send_photo(chat_id=CHANNEL_ID,photo=photo,caption=caption)
    else:
        bot.send_message(chat_id=CHANNEL_ID,text=caption)
    bot.send_message(chat_id=CHANNEL_ID,text=analysis_text+footer_text)
    bot.answer_callback_query(call.id,"News sent to channel ✅")

@bot.callback_query_handler(func=lambda call: call.data.startswith("bale_"))
def send_selected_news_bale(call: CallbackQuery):
    idx=int(call.data.split("_")[1])
    news_list=user_news_cache.get(call.message.chat.id)
    if not news_list or idx>=len(news_list):
        bot.answer_callback_query(call.id,"News not found ❌")
        return
    news=news_list[idx]
    title_fa=translator.translate(news["title"])
    analysis_text=analyze_news_with_gemini(news["description"])
    caption=f"📢 {title_fa}"
    full_text=caption+"\n\n"+analysis_text+footer_text
    image_path=None
    if news["image"]:
        image_path=os.path.join(IMAGES_DIR,"latest.jpg")
        download_image(news["image"],image_path)
    send_to_bale(full_text,image_path)
    bot.answer_callback_query(call.id,"News sent to Bale ✅")
@bot.message_handler(func=lambda m: m.text and m.text.lower()=="send news")
def send_news_list_combined(message):
    news_list=get_latest_news()
    if not news_list:
        bot.send_message(message.chat.id,"No news found ❌")
        return
    user_news_cache[message.chat.id]=news_list
    for idx,news in enumerate(news_list):
        preview=news["description"][:200]+"..."
        text=f"📢 {news['title']}\n🗓 {news['pub_date']}\n\n{preview}"
        keyboard=InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📤 Send News",callback_data=f"sendboth_{idx}"))
        bot.send_message(message.chat.id,text,reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sendboth_"))
def send_selected_news_both(call: CallbackQuery):
    idx=int(call.data.split("_")[1])
    news_list=user_news_cache.get(call.message.chat.id)
    if not news_list or idx>=len(news_list):
        bot.answer_callback_query(call.id,"News not found ❌")
        return
    news=news_list[idx]
    title_fa=translator.translate(news["title"])
    analysis_text=analyze_news_with_gemini(news["description"])
    caption=f"📢 {title_fa}"
    full_text=caption+"\n\n"+analysis_text+footer_text

    # ارسال به تلگرام
    if news["image"]:
        image_path=os.path.join(IMAGES_DIR,"latest.jpg")
        download_image(news["image"],image_path)
        with open(image_path,"rb") as photo:
            bot.send_photo(chat_id=CHANNEL_ID,photo=photo,caption=caption)
    else:
        bot.send_message(chat_id=CHANNEL_ID,text=caption)
    bot.send_message(chat_id=CHANNEL_ID,text=analysis_text+footer_text)

    # ارسال به بله
    image_path=None
    if news["image"]:
        image_path=os.path.join(IMAGES_DIR,"latest.jpg")
        download_image(news["image"],image_path)
    send_to_bale(full_text,image_path)

    bot.answer_callback_query(call.id,"News sent to Telegram & Bale ✅")
@app.route("/",methods=["POST"])
def webhook():
    json_string=request.get_data().decode("utf-8")
    update=telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "ok"

if __name__=="__main__":
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
