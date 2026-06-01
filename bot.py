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
preview_cache = {}  # ذخیره پیش‌نمایش برای جلوگیری از پردازش مجدد

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
    # بررسی در کش برای جلوگیری از پردازش مجدد
    cache_key = hash(description[:200])
    if cache_key in preview_cache:
        return preview_cache[cache_key]["analysis"]
    
    prompt = f"""
    تو یک خبرنگار حرفه‌ای هستی. متن طولانی خبری زیر را به یک خبر کوتاه و مفید در ۳ تا ۴ پاراگراف تبدیل کن.

قوانین:
پاراگراف اول: شامل چه کسی، چه اتفاقی، کجا، کی (Who, What, Where, When) همراه با مهمترین عدد یا آمار.

پاراگراف دوم: جزئیات تکمیلی و چرایی اصلی رویداد (Why).

پاراگراف سوم (و در صورت نیاز چهارم): پیامد فوری، واکنش مسئول یا تأثیر خبر.

سبک: خشک، بی‌طرف، روان و ساده. حذف نقل قول مستقیم و توضیحات اضافی.به جای گذاشتن اطلاعات اضافی، اصلاعات اصلی را نگه دار و در ضمن فرد باید فرد فقط خواندن این تحلیل بتواند کل متن خبر را بفهمد. هیچ قسمتی از متن را بولد یا پررنگ نکن. طول کل حداکثر ۱۰۰ کلمه.
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
    
def send_to_bale(text, image_path=None):
    try:
        if image_path:
            url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendPhoto"
            with open(image_path, "rb") as photo:
                r = requests.post(url, data={"chat_id": BALE_CHAT_ID}, files={"photo": photo})
                print("Bale photo:", r.text)
        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": BALE_CHAT_ID, "text": text})
        print("Bale message:", r.text)
    except Exception as e:
        print("Bale error:", e)
        
footer_text = """
\n📌 برای دنبال کردن آخرین اخبار و مطالب دنیای تکنولوژی و هوش مصنوعی، کانال‌های ما را مشاهده کنید:

💬 تلگرام:
https://t.me/MBB_Software_Group
https://t.me/hooshmalinovin

📱 بله:
https://ble.ir/MBB_Software_Group
"""

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "send news")
def send_news_list_combined(message):
    news_list = get_latest_news()
    if not news_list:
        bot.send_message(message.chat.id, "خبری یافت نشد ❌")
        return
    
    user_news_cache[message.chat.id] = news_list
    
    for idx, news in enumerate(news_list):
        # پردازش کامل خبر برای کش کردن
        cache_key = hash(news["description"][:200])
        if cache_key not in preview_cache:
            title_fa = translator.translate(news["title"])
            analysis_text = analyze_news_with_gemini(news["description"])
            caption = f"📢 {title_fa}"
            full_text = caption + "\n\n" + analysis_text + footer_text
            
            preview_cache[cache_key] = {
                "title_fa": title_fa,
                "analysis": analysis_text,
                "caption": caption,
                "full_text": full_text,
                "image_url": news["image"]
            }
        
        preview = news["description"][:200] + "..."
        text = f"📢 {news['title']}\n🗓 {news['pub_date']}\n\n{preview}"
        
        keyboard = InlineKeyboardMarkup(row_width=3)
        btn_telegram = InlineKeyboardButton("📤 ارسال به تلگرام", callback_data=f"tg_{idx}")
        btn_bale = InlineKeyboardButton("📱 ارسال به بله", callback_data=f"bl_{idx}")
        btn_both = InlineKeyboardButton("🔄 ارسال به هر دو", callback_data=f"both_{idx}")
        keyboard.add(btn_telegram, btn_bale, btn_both)
        
        bot.send_message(message.chat.id, text, reply_markup=keyboard)

def show_preview_and_confirm(chat_id, news_idx, target):
    """نمایش پیش‌نمایش و دریافت تأیید نهایی"""
    news_list = user_news_cache.get(chat_id)
    if not news_list or news_idx >= len(news_list):
        bot.send_message(chat_id, "خبر یافت نشد ❌")
        return None
    
    news = news_list[news_idx]
    cache_key = hash(news["description"][:200])
    cached = preview_cache.get(cache_key)
    
    if not cached:
        return None
    
    # ارسال پیش‌نمایش
    preview_text = f"""📋 **پیش‌نمایش خبر:**

{cached['full_text']}

---
✅ آیا برای ارسال تأیید می‌کنید؟"""

    keyboard = InlineKeyboardMarkup(row_width=2)
    btn_confirm = InlineKeyboardButton("✅ تأیید و ارسال", callback_data=f"confirm_{target}_{news_idx}")
    btn_cancel = InlineKeyboardButton("❌ لغو", callback_data=f"cancel_{chat_id}")
    keyboard.add(btn_confirm, btn_cancel)
    
    # ارسال تصویر در صورت وجود
    if cached['image_url']:
        image_path = os.path.join(IMAGES_DIR, f"preview_{news_idx}.jpg")
        download_image(cached['image_url'], image_path)
        with open(image_path, "rb") as photo:
            bot.send_photo(chat_id=chat_id, photo=photo, caption=preview_text, 
                          reply_markup=keyboard, parse_mode="Markdown")
        return image_path
    else:
        bot.send_message(chat_id, preview_text, reply_markup=keyboard, parse_mode="Markdown")
        return None

@bot.callback_query_handler(func=lambda call: call.data.startswith(("tg_", "bl_", "both_")))
def handle_destination_selection(call: CallbackQuery):
    """مدیریت انتخاب مقصد و نمایش پیش‌نمایش"""
    target, idx = call.data.split("_")
    idx = int(idx)
    
    # ذخیره انتخاب کاربر در کش
    if call.message.chat.id not in user_news_cache:
        user_news_cache[call.message.chat.id] = {}
    user_news_cache[call.message.chat.id]["selected_target"] = target
    user_news_cache[call.message.chat.id]["selected_idx"] = idx
    
    # نمایش پیش‌نمایش
    show_preview_and_confirm(call.message.chat.id, idx, target)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def send_confirmed_news(call: CallbackQuery):
    """ارسال نهایی پس از تأیید پیش‌نمایش"""
    parts = call.data.split("_")
    target = parts[1]
    idx = int(parts[2])
    
    chat_id = call.message.chat.id
    news_list = user_news_cache.get(chat_id)
    
    if not news_list or idx >= len(news_list):
        bot.answer_callback_query(call.id, "خبر یافت نشد ❌")
        return
    
    news = news_list[idx]
    cache_key = hash(news["description"][:200])
    cached = preview_cache.get(cache_key)
    
    if not cached:
        bot.answer_callback_query(call.id, "خطا در پردازش خبر ❌")
        return
    
    # ارسال بر اساس هدف انتخاب شده
    image_path = None
    if cached['image_url']:
        image_path = os.path.join(IMAGES_DIR, f"final_{idx}.jpg")
        download_image(cached['image_url'], image_path)
    
    if target == "tg" or target == "both":
        # ارسال به تلگرام
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as photo:
                bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=cached['caption'])
        else:
            bot.send_message(chat_id=CHANNEL_ID, text=cached['caption'])
        bot.send_message(chat_id=CHANNEL_ID, text=cached['analysis'] + footer_text)
    
    if target == "bl" or target == "both":
        # ارسال به بله
        send_to_bale(cached['full_text'], image_path)
    
    # پاکسازی فایل موقت
    if image_path and os.path.exists(image_path):
        os.remove(image_path)
    
    # پیام تأیید به کاربر
    if target == "tg":
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption="✅ خبر با موفقیت به **تلگرام** ارسال شد!",
            parse_mode="Markdown"
        )
    elif target == "bl":
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption="✅ خبر با موفقیت به **بله** ارسال شد!",
            parse_mode="Markdown"
        )
    else:
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption="✅ خبر با موفقیت به **هر دو** پلتفرم ارسال شد!",
            parse_mode="Markdown"
        )
    
    bot.answer_callback_query(call.id, "خبر ارسال شد ✅")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cancel_send(call: CallbackQuery):
    """لغو ارسال خبر"""
    bot.edit_message_caption(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        caption="❌ ارسال خبر لغو شد."
    )
    bot.answer_callback_query(call.id, "لغو شد")

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
